#!/usr/bin/env python3
"""A minimal private-cloud control plane that speaks the EC2 Query API.

Eucalyptus mattered because it implemented AWS's API, so the same tools and
scripts worked against hardware you owned. That is the idea this file tests:
the *contract* is the product, not the hypervisor.

What is here:

  * four EC2 actions — DescribeAvailabilityZones, DescribeImages, RunInstances,
    DescribeInstances and TerminateInstances
  * the EC2 XML envelope, because the Query API never moved to JSON
  * Signature Version 4 verified on every request, reusing the signer written in
    module 04 (`../week04/sigv4.py`) — the same code that signs is the code that
    checks, so a mismatch is a real mismatch
  * a refusal path: unsigned requests get 400, wrongly signed ones get 403

Nothing here is a product. It is the smallest thing that behaves like a control
plane, so that "private cloud" stops being a diagram.

Run:  python3 minicloud.py            # serves http://127.0.0.1:8773/
      python3 minicloud.py --quiet    # no per-request log lines
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "week04"))
import sigv4  # noqa: E402  — the module 04 implementation, reused server-side

HOST = "127.0.0.1"
PORT = 8773  # the port a Eucalyptus Cloud Controller listens on

# One tenant, one credential pair. This is a lab, and it says so.
ACCESS_KEY = "AKIDPRIVATECLOUDLAB"
SECRET_KEY = "lab-only-not-a-real-secret-key-0000000000"
REGION = "eucalyptus"
SERVICE = "ec2"

ZONES = {
    "building-a": {"max": 24, "free": 19},
    "building-b": {"max": 24, "free": 12},
}

IMAGES = {
    "emi-1A2B3C4D": {"name": "ubuntu-22.04-lab", "kernel": "eki-1A2B3C4D", "ramdisk": "eri-1A2B3C4D"},
    "emi-5E6F7A8B": {"name": "debian-12-hardened", "kernel": "eki-5E6F7A8B", "ramdisk": "eri-5E6F7A8B"},
}

STATE_CODES = {"pending": 0, "running": 16, "shutting-down": 32, "terminated": 48}


class Cloud:
    """In-memory instance state, guarded by a lock because requests are threaded."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.instances: dict[str, dict] = {}
        self.next_ip = 10

    def launch(self, image_id: str, zone: str, instance_type: str) -> dict:
        with self.lock:
            ok = image_id in IMAGES and zone in ZONES
            if not ok:
                return {}
            instance_id = "i-" + uuid.uuid4().hex[:8]
            address = f"10.0.0.{self.next_ip}"
            self.next_ip += 1
            record = {
                "id": instance_id,
                "image": image_id,
                "type": instance_type,
                "zone": zone,
                "state": "pending",
                "ip": address,
                "launched": time.time(),
            }
            self.instances[instance_id] = record
            ZONES[zone]["free"] -= 1
        threading.Thread(target=self._boot, args=(instance_id,), daemon=True).start()
        return record

    def _boot(self, instance_id: str) -> None:
        """A real launch takes seconds; so does this one, visibly."""
        time.sleep(1.2)
        with self.lock:
            if instance_id in self.instances:
                self.instances[instance_id]["state"] = "running"

    def terminate(self, instance_id: str) -> bool:
        with self.lock:
            record = self.instances.get(instance_id)
            if not record or record["state"] == "terminated":
                return False
            record["state"] = "shutting-down"
            zone = record["zone"]
        threading.Thread(target=self._shutdown, args=(instance_id, zone), daemon=True).start()
        return True

    def _shutdown(self, instance_id: str, zone: str) -> None:
        time.sleep(0.8)
        with self.lock:
            record = self.instances.get(instance_id)
            if record:
                record["state"] = "terminated"
                ZONES[zone]["free"] += 1

    def snapshot(self) -> list[dict]:
        with self.lock:
            return [dict(record) for record in self.instances.values()]


CLOUD = Cloud()


# ----------------------------------------------------------------- responses

def _envelope(action: str, body: str) -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<{action}Response xmlns="http://ec2.amazonaws.com/doc/2016-11-15/">\n'
        f"  <requestId>{uuid.uuid4()}</requestId>\n"
        f"{body}"
        f"</{action}Response>\n"
    )
    return xml.encode("utf-8")


def _error(code: str, message: str) -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        "  <Errors>\n"
        f"    <Error><Code>{code}</Code><Message>{message}</Message></Error>\n"
        "  </Errors>\n"
        f"  <RequestID>{uuid.uuid4()}</RequestID>\n"
        "</Response>\n"
    )
    return xml.encode("utf-8")


def _instance_item(record: dict) -> str:
    return (
        "        <item>\n"
        f"          <instanceId>{record['id']}</instanceId>\n"
        f"          <imageId>{record['image']}</imageId>\n"
        "          <instanceState>"
        f"<code>{STATE_CODES.get(record['state'], 0)}</code>"
        f"<name>{record['state']}</name>"
        "</instanceState>\n"
        f"          <privateIpAddress>{record['ip']}</privateIpAddress>\n"
        f"          <instanceType>{record['type']}</instanceType>\n"
        f"          <placement><availabilityZone>{record['zone']}</availabilityZone></placement>\n"
        "          <launchTime>"
        f"{datetime.fromtimestamp(record['launched'], timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
        "</launchTime>\n"
        "        </item>\n"
    )


def handle(action: str, params: dict[str, list[str]]) -> tuple[int, bytes]:
    def first(name: str, default: str = "") -> str:
        return params.get(name, [default])[0]

    if action == "DescribeAvailabilityZones":
        items = "".join(
            "    <item>\n"
            f"      <zoneName>{name}</zoneName>\n"
            "      <zoneState>available</zoneState>\n"
            f"      <maxInstances>{data['max']}</maxInstances>\n"
            f"      <freeInstances>{data['free']}</freeInstances>\n"
            "    </item>\n"
            for name, data in ZONES.items()
        )
        return 200, _envelope(action, f"  <availabilityZoneInfo>\n{items}  </availabilityZoneInfo>\n")

    if action == "DescribeImages":
        items = "".join(
            "    <item>\n"
            f"      <imageId>{image_id}</imageId>\n"
            f"      <name>{data['name']}</name>\n"
            f"      <kernelId>{data['kernel']}</kernelId>\n"
            f"      <ramdiskId>{data['ramdisk']}</ramdiskId>\n"
            "      <imageState>available</imageState>\n"
            "    </item>\n"
            for image_id, data in IMAGES.items()
        )
        return 200, _envelope(action, f"  <imagesSet>\n{items}  </imagesSet>\n")

    if action == "RunInstances":
        image_id = first("ImageId")
        zone = first("Placement.AvailabilityZone", "building-a")
        instance_type = first("InstanceType", "m1.small")
        if not image_id:
            return 400, _error("MissingParameter", "The request must contain the parameter ImageId")
        record = CLOUD.launch(image_id, zone, instance_type)
        if not record:
            return 400, _error("InvalidParameterValue", f"No such image or zone: {image_id} / {zone}")
        body = (
            "  <reservationId>r-" + uuid.uuid4().hex[:8] + "</reservationId>\n"
            "  <instancesSet>\n" + _instance_item(record) + "  </instancesSet>\n"
        )
        return 200, _envelope(action, body)

    if action == "DescribeInstances":
        wanted = set(params.get("InstanceId", []))
        records = CLOUD.snapshot()
        if wanted:
            records = [r for r in records if r["id"] in wanted]
        if not records:
            return 200, _envelope(action, "  <reservationSet></reservationSet>\n")
        body = "  <reservationSet>\n    <item>\n" \
               "      <reservationId>r-00000001</reservationId>\n" \
               "      <instancesSet>\n" + "".join(_instance_item(r) for r in records) + \
               "      </instancesSet>\n" \
               "    </item>\n" \
               "  </reservationSet>\n"
        return 200, _envelope(action, body)

    if action == "TerminateInstances":
        instance_id = first("InstanceId")
        if not instance_id:
            return 400, _error("MissingParameter", "The request must contain the parameter InstanceId")
        if not CLOUD.terminate(instance_id):
            return 400, _error("InvalidInstanceID.NotFound", f"The instance ID '{instance_id}' does not exist")
        body = (
            "  <instancesSet>\n    <item>\n"
            f"      <instanceId>{instance_id}</instanceId>\n"
            "      <currentState><code>32</code><name>shutting-down</name></currentState>\n"
            "      <previousState><code>16</code><name>running</name></previousState>\n"
            "    </item>\n  </instancesSet>\n"
        )
        return 200, _envelope(action, body)

    return 400, _error("InvalidAction", f"The action {action} is not valid for this service")


# ---------------------------------------------------------------- signature

def _canonical_query(params: dict[str, list[str]]) -> str:
    pairs = []
    for key in sorted(params):
        for value in sorted(params[key]):
            pairs.append(f"{quote(key, safe='-_.~')}={quote(value, safe='-_.~')}")
    return "&".join(pairs)


def check_signature(headers, method: str, path: str, params: dict[str, list[str]]) -> tuple[bool, str]:
    """Recompute the signature from the request exactly as received."""
    authorization = headers.get("Authorization", "")
    if not authorization:
        return False, "no Authorization header"

    match = re.match(
        r"AWS4-HMAC-SHA256 Credential=([^/]+)/([^,]+), SignedHeaders=([^,]+), Signature=([0-9a-f]{64})",
        authorization,
    )
    if not match:
        return False, "malformed Authorization header"

    access_key, scope, signed_headers, presented = match.groups()
    if access_key != ACCESS_KEY:
        return False, "unknown access key"

    timestamp = headers.get("X-Amz-Date", "")
    if not timestamp:
        return False, "no X-Amz-Date header"

    scope_parts = scope.split("/")
    if len(scope_parts) != 4:
        return False, "malformed credential scope"
    date, region, service, terminator = scope_parts
    if (region, service, terminator) != (REGION, SERVICE, "aws4_request"):
        return False, f"wrong scope: {region}/{service}/{terminator}"

    signed = {"Host": headers.get("Host", ""), "X-Amz-Date": timestamp}
    expected = sigv4.sign(
        method, path, _canonical_query(params), signed, b"", ACCESS_KEY, SECRET_KEY, REGION, SERVICE, timestamp
    )["signature"]

    import hmac as _hmac  # local import: only this check needs it
    if not _hmac.compare_digest(expected, presented):
        return False, "signature does not match"

    # Replay protection: the same rule AWS applies, one line of it.
    try:
        sent = datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False, "unparseable X-Amz-Date"
    if abs((datetime.now(timezone.utc) - sent).total_seconds()) > 300:
        return False, "X-Amz-Date is more than five minutes old"

    if signed_headers != "host;x-amz-date":
        return False, f"unexpected SignedHeaders: {signed_headers}"
    return True, "ok"


# ------------------------------------------------------------------- server

class Handler(BaseHTTPRequestHandler):
    server_version = "MiniCloud/0.1 (EC2 Query compatible)"
    protocol_version = "HTTP/1.1"
    quiet = False

    def log_message(self, fmt: str, *args) -> None:
        if not self.quiet:
            sys.stderr.write(f"{time.strftime('%H:%M:%S')} {fmt % args}\n")

    def _respond(self, status: int, payload: bytes, action: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/xml;charset=UTF-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("x-amzn-RequestId", str(uuid.uuid4()))
        self.end_headers()
        self.wfile.write(payload)
        if not self.quiet:
            print(f"  → {action}: {status} {self.responses.get(status, '')}", flush=True)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        params = parse_qs(parsed.query, keep_blank_values=True)
        action = params.get("Action", [""])[0]

        if not action:
            self._respond(400, _error("MissingParameter", "The request must contain the parameter Action"), "?")
            return

        ok, reason = check_signature(self.headers, "GET", parsed.path or "/", params)
        if not ok:
            code = "AuthFailure" if "header" not in reason else "MissingAuthenticationToken"
            self._respond(403 if "header" not in reason else 400,
                          _error(code, f"AWS was not able to validate the provided access credentials: {reason}"),
                          action)
            return

        status, payload = handle(action, params)
        self._respond(status, payload, action)


def serve(quiet: bool = False) -> ThreadingHTTPServer:
    Handler.quiet = quiet
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    return httpd


def main() -> int:
    quiet = "--quiet" in sys.argv
    httpd = serve(quiet=quiet)
    print(f"minicloud listening on http://{HOST}:{PORT}/  (EC2 Query API, SigV4 required)")
    print(f"access key {ACCESS_KEY} · region {REGION} · zones {', '.join(ZONES)}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
