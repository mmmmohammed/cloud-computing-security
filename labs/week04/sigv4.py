#!/usr/bin/env python3
"""AWS Signature Version 4, written from the specification, with no SDK.

Two things are checked here, and neither needs an AWS account:

1.  **The published test vector.** AWS documents a worked example — a GET to
    `example.amazonaws.com` with a fixed key, date and service. The expected
    signature is a constant, so matching it proves the implementation is right,
    not merely self-consistent.
2.  **Every intermediate value is printed.** The canonical request, the string
    to sign and the derived signing key are the parts that make signing
    teachable; they are also the parts that go wrong.

Run:  python3 sigv4.py
Exit: 0 if the test vector matches, 1 otherwise.
"""
from __future__ import annotations

import hashlib
import hmac
import sys

ALGORITHM = "AWS4-HMAC-SHA256"

# The worked example from the AWS documentation ("Signature Calculations for the
# Authorization Header"). These are AWS's published example values, not real keys.
EXAMPLE_ACCESS_KEY = "AKIDEXAMPLE"
EXAMPLE_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
EXAMPLE_REGION = "us-east-1"
EXAMPLE_SERVICE = "service"
EXAMPLE_TIMESTAMP = "20150830T123600Z"
EXPECTED_SIGNATURE = "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31"


def _hmac_sha256(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def signing_key(secret_key: str, datestamp: str, region: str, service: str) -> bytes:
    """Derive the per-day, per-region, per-service signing key.

    Note the chaining: each step signs the previous result, so the secret key
    never leaves the client and the derived key is useless after the day ends.
    """
    k_date = _hmac_sha256(("AWS4" + secret_key).encode("utf-8"), datestamp)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    return _hmac_sha256(k_service, "aws4_request")


def canonical_request(method: str, path: str, query: str, headers: dict[str, str], payload: bytes) -> str:
    """Step 1: a normalised request that both sides can reproduce exactly."""
    ordered = sorted(headers, key=str.lower)
    canonical_headers = "\n".join(f"{name.lower()}:{headers[name].strip()}" for name in ordered)
    signed_headers = ";".join(name.lower() for name in ordered)
    return "\n".join([
        method.upper(),
        path or "/",
        query,
        canonical_headers,
        "",
        signed_headers,
        sha256_hex(payload),
    ])


def string_to_sign(timestamp: str, scope: str, request: str) -> str:
    """Step 2: bind the request hash to the algorithm, the time and the scope."""
    return "\n".join([ALGORITHM, timestamp, scope, sha256_hex(request.encode("utf-8"))])


def scope_for(timestamp: str, region: str, service: str) -> str:
    return f"{timestamp[:8]}/{region}/{service}/aws4_request"


def sign(method: str, path: str, query: str, headers: dict[str, str], payload: bytes,
         access_key: str, secret_key: str, region: str, service: str, timestamp: str) -> dict[str, str]:
    """Return every intermediate value plus the Authorization header."""
    scope = scope_for(timestamp, region, service)
    canonical = canonical_request(method, path, query, headers, payload)
    to_sign = string_to_sign(timestamp, scope, canonical)
    key = signing_key(secret_key, timestamp[:8], region, service)
    signature = hmac.new(key, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    signed_headers = ";".join(name.lower() for name in sorted(headers, key=str.lower))
    authorization = (
        f"{ALGORITHM} Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "canonical_request": canonical,
        "string_to_sign": to_sign,
        "scope": scope,
        "signing_key_hex": key.hex(),
        "signature": signature,
        "authorization": authorization,
    }


def check_test_vector() -> dict[str, str]:
    headers = {"Host": "example.amazonaws.com", "X-Amz-Date": EXAMPLE_TIMESTAMP}
    result = sign(
        method="GET",
        path="/",
        query="",
        headers=headers,
        payload=b"",
        access_key=EXAMPLE_ACCESS_KEY,
        secret_key=EXAMPLE_SECRET_KEY,
        region=EXAMPLE_REGION,
        service=EXAMPLE_SERVICE,
        timestamp=EXAMPLE_TIMESTAMP,
    )
    result["expected"] = EXPECTED_SIGNATURE
    result["match"] = str(result["signature"] == EXPECTED_SIGNATURE)
    return result


def main() -> int:
    print("AWS Signature Version 4 — implementation check")
    print("no AWS account, no credentials, no network\n")

    r = check_test_vector()

    print("step 1 · canonical request")
    for line in r["canonical_request"].split("\n"):
        print(f"    {line}")
    print("\nstep 2 · string to sign")
    for line in r["string_to_sign"].split("\n"):
        print(f"    {line}")
    print(f"\nstep 3 · signing key (HMAC chain, hex)\n    {r['signing_key_hex']}")
    print(f"\nstep 4 · signature\n    {r['signature']}")
    print(f"\nstep 5 · expected by AWS\n    {EXPECTED_SIGNATURE}")

    ok = r["match"] == "True"
    print(f"\n{'MATCH — implementation agrees with the published vector' if ok else 'MISMATCH — implementation is wrong'}")
    print(f"\nauthorization header as it would be sent:\n    {r['authorization']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
