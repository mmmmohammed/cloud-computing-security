"""Week 3 lab, the part that can run without a cloud account.

The lab asks for the same page in three service models: nginx on an EC2
instance (IaaS), the same page on Elastic Beanstalk (PaaS), and a form in
Google Forms (SaaS). I have no AWS or Google account here, so this measures the
part I can: what it costs to serve that page yourself, versus handing it to a
runtime that does the serving for you.

  IaaS stand-in   nginx, user-space, configured by hand in nginx.conf
  PaaS stand-in   python3 -m http.server (one command, zero configuration)
  SaaS            not replicated: it needs a third-party account

What is measured: time from launch to first 200, non-comment config lines,
response headers, whether the server advertises its version, and whether a
request for a subdirectory gets a file listing.
"""
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
NGINX_ROOT = os.path.join(BASE, "nginx")
SITE = os.path.join(BASE, "site")
NGINX_PORT = 8081
PY_PORT = 8082


def wait_for(port, path="/hello.html", timeout=8.0, start_time=None):
    """Seconds until the server answers 200, or None. Timed from launch."""
    start = start_time if start_time is not None else time.perf_counter()
    while time.perf_counter() - start < timeout:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", path)
            response = conn.getresponse()
            response.read()
            conn.close()
            if response.status == 200:
                return round(time.perf_counter() - start, 2)
        except OSError:
            time.sleep(0.05)
    return None


def probe(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    response = conn.getresponse()
    body = response.read().decode("utf-8", "replace")
    headers = {k.lower(): v for k, v in response.getheaders()}
    ttfb = []
    for _ in range(5):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        t0 = time.perf_counter()
        c.request("GET", path)
        r = c.getresponse()
        r.read()
        ttfb.append((time.perf_counter() - t0) * 1000)
        c.close()
    conn.close()
    return {
        "status": response.status,
        "headers": headers,
        "ttfb_ms": round(sum(ttfb) / len(ttfb), 2),
        "listing": "notes.txt" in body,
        "body_kb": round(len(body) / 1024, 2),
    }


def port_is_free(port):
    s = socket.socket()
    # both servers set SO_REUSEADDR, so a socket in TIME_WAIT is not a conflict
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


for p in (NGINX_PORT, PY_PORT):
    if not port_is_free(p):
        sys.exit(f"port {p} is already in use; stop whatever owns it first")

# make sure nginx has its runtime directories
for sub in ("logs", "tmp/client_body", "tmp/proxy", "tmp/fastcgi", "tmp/uwsgi", "tmp/scgi"):
    os.makedirs(os.path.join(NGINX_ROOT, sub), exist_ok=True)

print("starting the two servers ...")
t_nginx = time.perf_counter()
nginx = subprocess.Popen(
    ["nginx", "-p", NGINX_ROOT + "/", "-c", os.path.join(BASE, "nginx.conf")],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)
nginx_up = wait_for(NGINX_PORT, start_time=t_nginx)

t_python = time.perf_counter()
python_srv = subprocess.Popen(
    [sys.executable, "-m", "http.server", str(PY_PORT), "--bind", "127.0.0.1"],
    cwd=SITE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
python_up = wait_for(PY_PORT, start_time=t_python)

results = {}
try:
    if nginx_up is None:
        out = nginx.stdout.read() if nginx.stdout else ""
        print("nginx did not come up:", out[:400])
    else:
        home = probe(NGINX_PORT, "/hello.html")
        sub = probe(NGINX_PORT, "/sub/")
        results["nginx"] = {"start_s": nginx_up, **home,
                            "dir_listing": sub["listing"], "dir_status": sub["status"]}
    if python_up is None:
        print("python http.server did not come up")
    else:
        home = probe(PY_PORT, "/hello.html")
        sub = probe(PY_PORT, "/sub/")
        results["python"] = {"start_s": python_up, **home,
                             "dir_listing": sub["listing"], "dir_status": sub["status"]}
finally:
    python_srv.terminate()
    python_srv.wait(timeout=10)
    # TERM the master we started: `nginx -s quit` needs its own prefix/config
    # and silently does nothing if they do not line up.
    if nginx.poll() is None:
        nginx.terminate()
        try:
            nginx.wait(timeout=10)
        except subprocess.TimeoutExpired:
            nginx.kill()
            nginx.wait(timeout=5)

config_lines = 0
for line in open(os.path.join(BASE, "nginx.conf"), encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#"):
        config_lines += 1

print(f"\n{'':22s}{'nginx (IaaS)':>18s}{'python (PaaS-ish)':>20s}")
print("-" * 60)
print(f"{'config lines':22s}{config_lines:>18d}{0:>20d}")
for key, label in (("start_s", "start to first 200"), ("ttfb_ms", "TTFB"), ("body_kb", "response KB")):
    row = f"{label:22s}"
    for name in ("nginx", "python"):
        r = results.get(name)
        row += f"{str(r[key]) if r else 'n/a':>18s}" if name == "nginx" else f"{str(r[key]) if r else 'n/a':>20s}"
    print(row)

print(f"\n{'server header':22s}")
for name in ("nginx", "python"):
    r = results.get(name)
    print(f"  {name:8s} {r['headers'].get('server', 'none') if r else 'n/a'}")

print(f"\n{'directory listing':22s}")
for name in ("nginx", "python"):
    r = results.get(name)
    print(f"  {name:8s} {'EXPOSED /sub/' if r and r['dir_listing'] else 'not exposed'}")

out = {
    "config_lines_nginx": config_lines,
    "config_lines_python": 0,
    "results": {k: {kk: vv for kk, vv in v.items() if kk != "headers"} for k, v in results.items()},
    "server_headers": {k: v["headers"].get("server", "") for k, v in results.items()},
    "dir_listing": {k: v["dir_listing"] for k, v in results.items()},
    "dir_status": {k: v["dir_status"] for k, v in results.items()},
}
with open(os.path.join(BASE, "serve_compare.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("\nwrote serve_compare.json")
