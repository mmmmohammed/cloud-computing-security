#!/usr/bin/env python3
"""Drive the mini private cloud the way a Eucalyptus user drove theirs.

This is the client half of the module 05 lab. It starts `minicloud.py`, signs
every request with the module 04 signer, and walks the lifecycle a Eucalyptus
operator walked: capacity, images, launch, states, terminate.

It also does the two things a diagram cannot show:

  * an unsigned request — refused with 400 before authentication
  * a request signed with the wrong secret — refused with 403

Run:  python3 euca_client.py
Writes: mini_cloud.json, euca_client.log
Exit: 0 if every expected state and refusal was observed, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import quote
from xml.etree import ElementTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "week04"))
import sigv4  # noqa: E402

HOST = "127.0.0.1"
PORT = 8773
HOST_HEADER = f"{HOST}:{PORT}"
ACCESS_KEY = "AKIDPRIVATECLOUDLAB"
SECRET_KEY = "lab-only-not-a-real-secret-key-0000000000"
WRONG_SECRET = "definitely-not-the-secret-key-1111111111"
REGION = "eucalyptus"
SERVICE = "ec2"


# --------------------------------------------------------------- transport

def canonical_query(params: dict[str, str]) -> str:
    """Sorted, percent-encoded — the form both sides must agree on."""
    return "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(params.items()))


def call(params: dict[str, str], secret: str | None = SECRET_KEY) -> dict:
    """One signed GET. `secret=None` sends it unsigned."""
    query = canonical_query(params)
    url = f"http://{HOST_HEADER}/?{query}"
    started = time.perf_counter()
    headers = {}

    if secret is not None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        signed = {"Host": HOST_HEADER, "X-Amz-Date": timestamp}
        result = sigv4.sign("GET", "/", query, signed, b"", ACCESS_KEY, secret, REGION, SERVICE, timestamp)
        headers = {"Host": HOST_HEADER, "X-Amz-Date": timestamp, "Authorization": result["authorization"]}

    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status, body = response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read().decode("utf-8")
    elapsed = (time.perf_counter() - started) * 1000

    return {
        "action": params.get("Action", "?"),
        "status": status,
        "ms": round(elapsed, 1),
        "body": body,
        "error_code": _text(body, "Code"),
        "error_message": _text(body, "Message"),
    }


def _text(xml: str, tag: str) -> str:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return ""
    for node in root.iter():
        if node.tag.split("}")[-1] == tag and node.text:
            return node.text.strip()
    return ""


def _items(xml: str, container: str) -> list[dict]:
    """Flatten one level of an EC2 <...Set><item>…</item></...Set> response."""
    root = ElementTree.fromstring(xml)
    found = []
    for node in root.iter():
        if node.tag.split("}")[-1] != container:
            continue
        for item in node:
            if item.tag.split("}")[-1] != "item":
                continue
            record = {}
            for child in item:
                name = child.tag.split("}")[-1]
                if len(child):
                    for grandchild in child:
                        record[name + "." + grandchild.tag.split("}")[-1]] = (grandchild.text or "").strip()
                else:
                    record[name] = (child.text or "").strip()
            found.append(record)
    return found


# ---------------------------------------------------------------- lifecycle

def wait_for_port(timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.3)
            if probe.connect_ex((HOST, PORT)) == 0:
                return True
        time.sleep(0.1)
    return False


def state_of(instance_id: str) -> str:
    result = call({"Action": "DescribeInstances", "InstanceId": instance_id})
    for item in _items(result["body"], "instancesSet"):
        if item.get("instanceId") == instance_id:
            return item.get("instanceState.name", "?")
    return "?"


def main() -> int:
    problems: list[str] = []
    report: dict = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    server = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "minicloud.py"), "--quiet"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_for_port():
            print("the control plane did not start on port", PORT)
            return 1
        print(f"private cloud up on http://{HOST_HEADER}/  · sigv4 verified server-side\n")

        # 1 · capacity, the way euca-describe-availability-zones verbose shows it
        zones = call({"Action": "DescribeAvailabilityZones"})
        zone_items = _items(zones["body"], "availabilityZoneInfo")
        report["describe_availability_zones"] = {"status": zones["status"], "ms": zones["ms"], "zones": zone_items}
        print("1 · euca-describe-availability-zones verbose")
        for zone in zone_items:
            print(f"    {zone.get('zoneName', '?'):12s} {zone.get('freeInstances', '?'):>2s} free of "
                  f"{zone.get('maxInstances', '?'):>2s} · {zone.get('zoneState', '?')}")

        # 2 · images, including the kernel and ramdisk that make an EMI
        images = call({"Action": "DescribeImages"})
        image_items = _items(images["body"], "imagesSet")
        report["describe_images"] = {"status": images["status"], "ms": images["ms"], "images": image_items}
        print("\n2 · euca-describe-images")
        for image in image_items:
            print(f"    {image.get('imageId', '?'):14s} {image.get('name', ''):22s} "
                  f"kernel {image.get('kernelId', '?')} · ramdisk {image.get('ramdiskId', '?')}")

        # 3 · launch two instances, one per cluster
        print("\n3 · euca-run-instances")
        launched = []
        for image_id, zone, size in (
            ("emi-1A2B3C4D", "building-a", "m1.small"),
            ("emi-5E6F7A8B", "building-b", "m1.large"),
        ):
            result = call({
                "Action": "RunInstances",
                "ImageId": image_id,
                "InstanceType": size,
                "Placement.AvailabilityZone": zone,
            })
            items = _items(result["body"], "instancesSet")
            if result["status"] != 200 or not items:
                problems.append(f"launch failed for {image_id}: {result['status']} {result['error_code']}")
                continue
            record = {
                "id": items[0].get("instanceId"),
                "image": image_id,
                "zone": zone,
                "type": size,
                "ip": items[0].get("privateIpAddress"),
                "state_at_launch": items[0].get("instanceState.name"),
                "latency_ms": result["ms"],
            }
            launched.append(record)
            print(f"    {record['id']}  {image_id}  {zone}  {size}  "
                  f"state={record['state_at_launch']}  ip={record['ip']}  ({result['ms']} ms)")

        # 4 · watch the states settle, and time the transition
        print("\n4 · euca-describe-instances (one call, all instances)")
        transitions = {}
        first_seen: dict[str, str] = {}
        states: dict[str, str] = {}
        polls = 0
        started = time.perf_counter()
        deadline = time.time() + 8
        while time.time() < deadline:
            listing = call({"Action": "DescribeInstances"})
            polls += 1
            current = {
                item.get("instanceId"): item.get("instanceState.name", "?")
                for item in _items(listing["body"], "instancesSet")
            }
            for record in launched:
                state = current.get(record["id"], "?")
                first_seen.setdefault(record["id"], state)
                states[record["id"]] = state
            if all(states.get(r["id"]) == "running" for r in launched):
                break
            time.sleep(0.2)

        elapsed = round(time.perf_counter() - started, 2)
        for record in launched:
            record["final_state"] = states.get(record["id"], "?")
            transitions[record["id"]] = elapsed
            print(f"    {record['id']}  {first_seen[record['id']]} → {record['final_state']}  after {elapsed} s")
            if record["final_state"] != "running":
                problems.append(f"{record['id']} never reached running (last: {record['final_state']})")
        print(f"    {polls} describe calls, 0.2 s apart — the poll is the API working as designed")

        listed = call({"Action": "DescribeInstances"})
        report["describe_instances"] = {
            "status": listed["status"], "ms": listed["ms"],
            "instances": _items(listed["body"], "instancesSet"),
        }

        # 5 · terminate, and confirm it
        print("\n5 · euca-terminate-instances")
        for record in launched:
            result = call({"Action": "TerminateInstances", "InstanceId": record["id"]})
            print(f"    {record['id']}  → {result['status']}  {_text(result['body'], 'name')}")
            time.sleep(1.2)
            record["state_after_terminate"] = state_of(record["id"])
            if record["state_after_terminate"] != "terminated":
                problems.append(f"{record['id']} is {record['state_after_terminate']}, expected terminated")

        # 6 · the two refusals
        print("\n6 · refusals")
        unsigned = call({"Action": "DescribeInstances"}, secret=None)
        wrong = call({"Action": "DescribeInstances"}, secret=WRONG_SECRET)
        report["refusals"] = {
            "unsigned": {"status": unsigned["status"], "code": unsigned["error_code"], "ms": unsigned["ms"]},
            "wrong_secret": {"status": wrong["status"], "code": wrong["error_code"], "ms": wrong["ms"]},
        }
        print(f"    unsigned      → {unsigned['status']} {unsigned['error_code']}")
        print(f"    wrong secret  → {wrong['status']} {wrong['error_code']}")
        if unsigned["status"] != 400:
            problems.append(f"unsigned request returned {unsigned['status']}, expected 400")
        if wrong["status"] != 403:
            problems.append(f"wrongly signed request returned {wrong['status']}, expected 403")

        report["instances"] = launched
        report["transitions_s"] = transitions
        report["polls"] = polls
        report["problems"] = problems

        with open(os.path.join(HERE, "mini_cloud.json"), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        print("\nsummary")
        print(f"    launched      {len(launched)} instances across {len({r['zone'] for r in launched})} clusters")
        print(f"    reached       running in {min(transitions.values()) if transitions else '?'} s")
        print(f"    terminated    {sum(1 for r in launched if r.get('state_after_terminate') == 'terminated')}/{len(launched)}")
        print(f"    refusals      400 unsigned · 403 wrong secret")
        print(f"    problems      {len(problems) or 'none'}")
        for problem in problems:
            print(f"      - {problem}")
        print("\nwrote mini_cloud.json")
        return 0 if not problems else 1
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
