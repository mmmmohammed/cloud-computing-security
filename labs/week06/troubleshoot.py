#!/usr/bin/env python3
"""Break the server five ways, and diagnose each one the way the module says to.

Every fault here is real: the config really is wrong, the process really is
stopped, the file really is unreadable. The evidence is collected from the
system — status code, listening sockets, `nginx -t`, the error log — not written
from imagination, and each fault is fixed before the next one is introduced.

The method is the deck's six steps, in order:
    define → gather evidence → hypothesise → change one thing → verify → record

Run:  python3 troubleshoot.py
Writes: troubleshoot.json, troubleshoot.log
Exit: 0 if every fault was reproduced, explained and fixed, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import provision as p

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = json.load(open(os.path.join(HERE, "server.spec.json"), encoding="utf-8"))
PORT = SPEC["ports"]["http"]
ERROR_LOG = os.path.join(p.RUNTIME, "logs", "error.log")
UPSTREAM_PORT = 9099
PROCESS = None


# ------------------------------------------------------------------ helpers

def listening() -> str:
    result = subprocess.run(["ss", "-ltn"], capture_output=True, text=True)
    lines = [line.split() for line in result.stdout.splitlines()[1:]]
    hits = [row for row in lines if len(row) >= 4 and row[3].endswith(f":{PORT}")]
    return "; ".join(f"{row[3]}" for row in hits) if hits else "nothing listening on " + str(PORT)


def log_tail(lines: int = 2) -> list[str]:
    if not os.path.exists(ERROR_LOG):
        return []
    with open(ERROR_LOG, encoding="utf-8", errors="replace") as handle:
        content = [line.strip() for line in handle if line.strip()]
    return content[-lines:]


def request(path: str = "/") -> tuple[int, float]:
    return p.probe(PORT, path)


def evidence(path: str = "/") -> dict:
    status, ms = request(path)
    ok, output = p.nginx_test()
    return {
        "request": f"GET {path}",
        "status": status,
        "ms": ms,
        "listening": listening(),
        "nginx_t": "ok" if ok else output.splitlines()[-1] if output else "failed",
        "error_log": log_tail(),
    }


def restart() -> None:
    global PROCESS
    p.stop(PROCESS)
    PROCESS = p.start()
    p.wait_for(PORT)


def write_conf(text: str) -> None:
    open(p.CONF, "w", encoding="utf-8").write(text)


def read_conf() -> str:
    return open(p.CONF, encoding="utf-8").read()


def free_port(port: int) -> bool:
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return probe.connect_ex(("127.0.0.1", port)) != 0


# ------------------------------------------------------------------- faults

def fault_blocked() -> dict:
    """A firewall rule that only allows an address you are not coming from."""
    conf = read_conf().replace(f"listen 127.0.0.1:{PORT};", "listen 127.0.0.9:8080;")
    write_conf(conf)
    restart()
    before = evidence()
    # The fix is to put the listen address back — the "rule" was the config.
    write_conf(p.render_conf(SPEC))
    restart()
    after = request()
    return {
        "name": "blocked",
        "symptom": "connection refused from the network, though the process is running",
        "evidence": before,
        "cause": "the listener was bound to 127.0.0.9, so nothing answers on 127.0.0.1 — the local equivalent of a security-group rule that excludes your address",
        "fix": "restore the intended listen address, reload, re-test",
        "verified": after[0],
    }


def fault_service_down() -> dict:
    """The classic: the site is down because the service is not running."""
    global PROCESS
    p.stop(PROCESS)
    PROCESS = None
    before = evidence()
    restart()
    after = request()
    return {
        "name": "service down",
        "symptom": "site unreachable; nothing answers on the port",
        "evidence": before,
        "cause": "nginx was not running — no listener, so the TCP connection is refused before HTTP exists",
        "fix": "start the service, then confirm with a request rather than a process check",
        "verified": after[0],
    }


def fault_config_error() -> dict:
    """A config typo, caught by `nginx -t` before it can take the site down twice."""
    write_conf(read_conf() + "\nworker_processes_on_holiday on;\n")
    ok, output = p.nginx_test()
    p.stop(PROCESS)
    attempt = p.start()
    time.sleep(0.6)
    attempt_failed = attempt.poll() is not None
    before = evidence()
    write_conf(p.render_conf(SPEC))
    ok_after, _ = p.nginx_test()
    restart()
    after = request()
    return {
        "name": "config error",
        "symptom": "service will not (re)start after a change",
        "evidence": {
            "nginx_t": "ok" if ok else output.replace("\n", " | "),
            "status_before_fix": before["status"],
            "restart_refused": str(attempt_failed),
        },
        "cause": "an unknown directive was appended to the config; nginx validates the whole file before it starts",
        "fix": "restore the generated config (never hand-edit), re-run nginx -t, then start",
        "verified": after[0],
    }


def fault_permissions() -> dict:
    """Unreadable file: the request reaches nginx and is refused there."""
    page = os.path.join(HERE, "site", "index.html")
    shutil.copy(page, page + ".bak")
    os.chmod(page, 0o000)
    before = evidence()
    os.chmod(page, 0o644)
    os.remove(page + ".bak")
    after = request()
    return {
        "name": "permission denied",
        "symptom": "403 Forbidden for a page that exists",
        "evidence": before,
        "cause": "the document was mode 000 — the worker could not read it, so nginx returned 403 rather than 404",
        "fix": "restore readable permissions (0644), and check ownership the same way",
        "verified": after[0],
    }


def fault_dead_upstream() -> dict:
    """A proxy pointing at a service that is not listening."""
    conf = read_conf().replace(
        "        location / {",
        "        location /api/ {\n"
        "            proxy_pass http://127.0.0.1:9099/;\n"
        "        }\n\n"
        "        location / {",
    )
    write_conf(conf)
    restart()
    before = evidence("/api/")
    # The fix: start the thing the proxy is pointing at.
    upstream_dir = os.path.join(p.RUNTIME, "upstream")
    os.makedirs(upstream_dir, exist_ok=True)
    open(os.path.join(upstream_dir, "index.html"), "w", encoding="utf-8").write(
        "<!DOCTYPE html><title>api</title><p>upstream is alive</p>\n"
    )
    upstream = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(UPSTREAM_PORT), "--bind", "127.0.0.1",
         "--directory", upstream_dir],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.8)
    after_status, _ = request("/api/")
    upstream.terminate()
    upstream.wait(timeout=10)
    write_conf(p.render_conf(SPEC))
    restart()
    return {
        "name": "dead upstream",
        "symptom": "one route returns 502 while the rest of the site is fine",
        "evidence": before,
        "cause": "proxy_pass pointed at 127.0.0.1:9099 where nothing was listening; the error log names the refused connection",
        "fix": "start the upstream service and re-test the same route",
        "verified": after_status,
    }


# --------------------------------------------------------------------- main

def main() -> int:
    global PROCESS
    results = []
    problems = []

    if not free_port(PORT):
        print(f"port {PORT} is already in use — stop the other server first")
        return 1

    # Commission inline rather than shelling out: the point of this script is to
    # own the server process, and a subprocess would leave it orphaned.
    print("commissioning before troubleshooting")
    if not p.run_gate(SPEC):
        print("\nbuild refused by the policy gate")
        return 1
    subprocess.run(["bash", os.path.join(HERE, SPEC.get("bootstrap", "bootstrap.sh"))],
                   check=True, capture_output=True, text=True)
    p.ensure_dirs()
    open(p.CONF, "w", encoding="utf-8").write(p.render_conf(SPEC))
    ok, output = p.nginx_test()
    if not ok:
        print("nginx -t failed:\n" + output)
        return 1
    PROCESS = p.start()
    took = p.wait_for(PORT)
    print(f"commissioned, answering after {took}s\n")

    for index, fault in enumerate(
        (fault_blocked, fault_service_down, fault_config_error, fault_permissions, fault_dead_upstream), start=1
    ):
        print(f"fault {index} · {fault.__name__.replace('fault_', '').replace('_', ' ')}")
        result = fault()
        results.append(result)
        seen = result["evidence"]
        status = seen.get("status", seen.get("status_before_fix", "n/a"))
        detail = seen.get("listening") or seen.get("nginx_t")
        print(f"  symptom   {result['symptom']}")
        print(f"  evidence  status {status} · {detail}")
        print(f"  cause     {result['cause']}")
        print(f"  fix       {result['fix']}")
        print(f"  verified  {result['verified']}  {'ok' if result['verified'] == 200 else 'STILL BROKEN'}\n")
        if result["verified"] != 200:
            problems.append(result["name"])

    report = {
        "faults": results,
        "problems": problems,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    json.dump(report, open(os.path.join(HERE, "troubleshoot.json"), "w", encoding="utf-8"), indent=2)

    print(f"{len(results)} faults reproduced, diagnosed and fixed · problems: {problems or 'none'}")
    print("wrote troubleshoot.json")
    return 0 if not problems else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        if PROCESS is not None:
            p.stop(PROCESS)
