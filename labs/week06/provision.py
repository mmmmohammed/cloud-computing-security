#!/usr/bin/env python3
"""Commission a server from a declarative spec — the repeatable path.

This is the module 06 lab's first half, and it is deliberately the same shape as
the real thing: a spec file, a policy gate that refuses to build an insecure
server, a bootstrap script that runs once, then a verification step that asks the
server whether it actually works.

What is real here:
  * a real nginx, started, configured and verified
  * a real policy gate — the bad spec in this folder is refused
  * a real build record with timings and file hashes

What is substituted: there is no hypervisor. The "instance" is a directory, the
"security group" is the listen address and port, and the "encrypted volume" is a
flag the gate enforces rather than something cryptsetup does. The page says so.

Run:  python3 provision.py                  # build from server.spec.json
      python3 provision.py --spec server.spec.bad.json   # watch the gate refuse
      python3 provision.py --stop
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.join(HERE, "runtime")
CONF = os.path.join(RUNTIME, "nginx.conf")
BUILD = os.path.join(RUNTIME, "build.json")

# Ports an internet-facing server may expose; anything else needs a reason.
PUBLIC_PORTS = {80, 443, 8080, 8443}


# ---------------------------------------------------------------- the gate

def policy_scan(spec: dict) -> list[tuple[str, bool, str]]:
    """Checks in the spirit of the CIS baseline, plus the two that catch rushed builds."""
    checks: list[tuple[str, bool, str]] = []

    ssh = spec.get("ssh_cidr", "")
    checks.append((
        "admin port not open to the internet",
        ssh not in ("0.0.0.0/0", "::/0", ""),
        f"ssh_cidr is {ssh!r} — 0.0.0.0/0 would expose SSH to every scanner on the internet",
    ))

    tokens = str(spec.get("imds_tokens", "")).lower()
    checks.append((
        "IMDSv2 enforced",
        tokens == "required",
        f"imds_tokens is {tokens!r} — 'required' blocks SSRF credential theft",
    ))

    checks.append((
        "root volume encrypted",
        bool(spec.get("encrypted_volume")),
        "encrypted_volume must be true",
    ))

    ports = set(int(v) for v in spec.get("ports", {}).values())
    unexpected = ports - PUBLIC_PORTS
    checks.append((
        "only HTTP/HTTPS exposed",
        not unexpected,
        f"unexpected public ports: {sorted(unexpected)}" if unexpected else "ok",
    ))

    bootstrap = os.path.join(HERE, spec.get("bootstrap", "bootstrap.sh"))
    text = ""
    if os.path.exists(bootstrap):
        text = open(bootstrap, encoding="utf-8", errors="replace").read()
    checks.append((
        "no access keys in bootstrap",
        "AKIA" not in text and "aws_secret_access_key" not in text,
        "bootstrap contains an access key — use an instance role instead",
    ))

    tags = spec.get("tags", {})
    checks.append((
        "ownership tagged",
        all(tags.get(key) for key in ("Owner", "Project")),
        "tags must include Owner and Project so the server can be found later",
    ))

    return checks


def run_gate(spec: dict, quiet: bool = False) -> bool:
    checks = policy_scan(spec)
    passed = all(ok for _, ok, _ in checks)
    if not quiet:
        print("policy gate")
        for name, ok, note in checks:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {name}" + ("" if ok else f"\n         {note}"))
    return passed


# --------------------------------------------------------------- the build

def render_conf(spec: dict) -> str:
    port = spec["ports"]["http"]
    root = os.path.join(HERE, "site")
    return f"""# rendered by provision.py from server.spec.json — do not edit by hand
worker_processes 1;
error_log logs/error.log warn;
pid logs/nginx.pid;

events {{ worker_connections 64; }}

http {{
    access_log off;
    server_tokens off;          # do not advertise the version
    default_type text/html;

    client_body_temp_path temp/client_body;
    proxy_temp_path       temp/proxy;
    fastcgi_temp_path     temp/fastcgi;
    uwsgi_temp_path       temp/uwsgi;
    scgi_temp_path        temp/scgi;

    server {{
        listen 127.0.0.1:{port};
        root {root};
        index index.html;
        autoindex off;          # no directory listings

        location / {{
            try_files $uri $uri/ =404;
        }}
    }}
}}
"""


def ensure_dirs() -> None:
    for path in ("logs", "temp/client_body", "temp/proxy", "temp/fastcgi", "temp/uwsgi", "temp/scgi"):
        os.makedirs(os.path.join(RUNTIME, path), exist_ok=True)


def nginx_test() -> tuple[bool, str]:
    result = subprocess.run(
        ["nginx", "-p", RUNTIME + "/", "-c", CONF, "-t"],
        capture_output=True, text=True,
    )
    return result.returncode == 0, (result.stderr or result.stdout).strip()


def start() -> subprocess.Popen:
    """`-g daemon off` keeps the master in our process tree, so we can stop it.

    Module 03 learned this the hard way: nginx daemonises by default and the
    process you launched is gone before the port check runs.
    """
    ensure_dirs()
    process = subprocess.Popen(
        ["nginx", "-p", RUNTIME + "/", "-c", CONF, "-g", "daemon off;"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return process


def stop(process: subprocess.Popen | None = None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return

    pid_file = os.path.join(RUNTIME, "logs", "nginx.pid")
    if os.path.exists(pid_file):
        try:
            pid = int(open(pid_file).read().strip())
            os.kill(pid, 15)
            time.sleep(0.5)
        except (ValueError, ProcessLookupError, PermissionError):
            pass


def probe(port: int, path: str = "/", timeout: float = 3.0) -> tuple[int, float]:
    url = f"http://127.0.0.1:{port}{path}"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read(2048)
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    except Exception:
        status = 0
    return status, round((time.perf_counter() - started) * 1000, 1)


def wait_for(port: int, timeout: float = 8.0) -> float | None:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout:
        status, _ = probe(port, timeout=0.5)
        if status:
            return round(time.perf_counter() - started, 2)
        time.sleep(0.1)
    return None


def sha256(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default=os.path.join(HERE, "server.spec.json"))
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()

    if args.stop:
        stop()
        print("stopped")
        return 0

    started = time.perf_counter()
    spec = json.load(open(args.spec, encoding="utf-8"))
    print(f"commissioning {spec['name']} from {os.path.basename(args.spec)}")
    print(f"  image {spec['image']} · type {spec['instance_type']} · region {spec['region']}\n")

    # 1 · the gate. Nothing is built until this passes.
    if not run_gate(spec):
        print("\nbuild refused — fix the spec, not the checker")
        return 1

    # 2 · bootstrap, the user-data equivalent
    print("\nbootstrap")
    result = subprocess.run(["bash", os.path.join(HERE, spec.get("bootstrap", "bootstrap.sh"))],
                            capture_output=True, text=True)
    for line in (result.stdout or "").splitlines():
        print("  " + line)
    if result.returncode != 0:
        print("  bootstrap failed:\n" + (result.stderr or ""))
        return 1

    # 3 · render and start
    print("\nrender and start")
    ensure_dirs()
    open(CONF, "w", encoding="utf-8").write(render_conf(spec))
    ok, output = nginx_test()
    print(f"  nginx -t: {'ok' if ok else 'FAILED'}")
    if not ok:
        print("  " + output.replace("\n", "\n  "))
        return 1

    stop()
    process = start()
    port = spec["ports"]["http"]
    took = wait_for(port)
    status, first_byte = probe(port)
    print(f"  listening on 127.0.0.1:{port} after {took}s" if took is not None
          else "  never came up")
    print(f"  GET / → {status} in {first_byte} ms")

    # 4 · verify and record
    if status != 200:
        print("\nverification failed — the server is up but not serving")
        stop(process)
        return 1

    total = round(time.perf_counter() - started, 2)
    record = {
        "spec": os.path.basename(args.spec),
        "name": spec["name"],
        "image": spec["image"],
        "instance_type": spec["instance_type"],
        "region": spec["region"],
        "ports": spec["ports"],
        "tags": spec.get("tags", {}),
        "time_to_serve_s": took,
        "commission_time_s": total,
        "first_request_ms": first_byte,
        "checks": [{"name": n, "passed": ok, "note": note} for n, ok, note in policy_scan(spec)],
        "config_sha256": sha256(CONF),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    json.dump(record, open(BUILD, "w", encoding="utf-8"), indent=2)

    print(f"\ncommissioned in {total}s — {len(record['checks'])} policy checks passed")
    print(f"  build record: runtime/build.json")
    print(f"  still running as pid {process.pid}; stop with: python3 provision.py --stop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
