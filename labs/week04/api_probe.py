#!/usr/bin/env python3
"""How a cloud API answers a request it does not accept.

Every action in the cloud is an API call, and the differences between the
responses below are the whole point of the module:

  * a public data endpoint answers with no authentication at all
  * a control-plane endpoint refuses an unsigned request
  * the same request, signed with a made-up key, is refused differently — which
    tells you the request was parsed and the signature was evaluated

Nothing here changes anything: every call is a read, and the credentials are the
fake ones from AWS's own documentation example.

Run:  python3 api_probe.py
Writes: api_probe.json, api_probe.log
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

import sigv4

EC2_HOST = "ec2.us-east-1.amazonaws.com"
EC2_PATH = "/"
EC2_QUERY = "Action=DescribeRegions&Version=2016-11-15"
IP_RANGES = "https://ip-ranges.amazonaws.com/ip-ranges.json"

FAKE_ACCESS_KEY = sigv4.EXAMPLE_ACCESS_KEY
FAKE_SECRET_KEY = sigv4.EXAMPLE_SECRET_KEY


def _error_code(body: str) -> str | None:
    match = re.search(r"<Code>([^<]+)</Code>", body)
    return match.group(1) if match else None


def _error_message(body: str) -> str | None:
    match = re.search(r"<Message>([^<]+)</Message>", body)
    return match.group(1) if match else None


def call(url: str, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    started = datetime.now(timezone.utc)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", "replace")
            status = response.status
            reason = response.reason
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        status = error.code
        reason = error.reason
    elapsed_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
    return {
        "url": url,
        "status": status,
        "reason": str(reason),
        "error_code": _error_code(body),
        "error_message": _error_message(body),
        "bytes": len(body),
        "ms": round(elapsed_ms, 1),
        "body_head": body[:300].replace("\n", " "),
    }


def signed_ec2_call() -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    headers = {
        "Host": EC2_HOST,
        "X-Amz-Date": timestamp,
    }
    result = sigv4.sign(
        method="GET",
        path=EC2_PATH,
        query=EC2_QUERY,
        headers=headers,
        payload=b"",
        access_key=FAKE_ACCESS_KEY,
        secret_key=FAKE_SECRET_KEY,
        region="us-east-1",
        service="ec2",
        timestamp=timestamp,
    )
    sent = {
        "Host": EC2_HOST,
        "X-Amz-Date": timestamp,
        "Authorization": result["authorization"],
    }
    outcome = call(f"https://{EC2_HOST}{EC2_PATH}?{EC2_QUERY}", sent)
    outcome["signature_sent"] = result["signature"]
    outcome["scope"] = result["scope"]
    return outcome


def main() -> None:
    print("cloud APIs, and three different ways to be told no\n")

    print("1 · a public data endpoint, no authentication")
    public = call(IP_RANGES)
    print(f"    GET ip-ranges.amazonaws.com  →  {public['status']} {public['reason']} · {public['bytes']:,} bytes · {public['ms']} ms")

    print("\n2 · a control-plane endpoint, unsigned")
    unsigned = call(f"https://{EC2_HOST}{EC2_PATH}?{EC2_QUERY}")
    print(f"    GET {EC2_HOST}  →  {unsigned['status']} {unsigned['reason']} · {unsigned['error_code']} · {unsigned['ms']} ms")
    print(f"    {unsigned['error_message']}")

    print("\n3 · the same call, signed with AWS's published example key")
    signed = signed_ec2_call()
    print(f"    signature sent     : {signed['signature_sent'][:32]}…")
    print(f"    scope              : {signed['scope']}")
    print(f"    GET {EC2_HOST}  →  {signed['status']} {signed['reason']} · {signed['error_code']} · {signed['ms']} ms")
    print(f"    {signed['error_message']}")

    print("\nwhat the three answers mean")
    print("    public   : no identity needed — this is data AWS publishes on purpose")
    print("    unsigned : rejected at parameter validation, before authentication starts;")
    print("               the API names what is missing (AWSAccessKeyId)")
    print("    signed   : the Authorization header was parsed and the credentials evaluated,")
    print("               then refused — the key is AWS's published example, not a real one")

    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "public_endpoint": public,
        "unsigned": unsigned,
        "signed": signed,
    }
    with open("api_probe.json", "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print("\nwrote api_probe.json")


if __name__ == "__main__":
    main()
