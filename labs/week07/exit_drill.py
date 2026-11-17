#!/usr/bin/env python3
"""Rehearse an exit from a proprietary store.

The deck's lesson on lock-in is not "avoid the cloud" — it is "rehearse an
exit". This does exactly that on a local stand-in for a proprietary NoSQL
service: read every document, convert it to two open formats plus SQLite,
prove the export is complete and faithful, and cost the transfer.

Nothing here talks to a provider. The store, the formats and the arithmetic
are real; the price per gigabyte is the published data-transfer-out rate.
"""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import sqlite3
import time

HERE = pathlib.Path(__file__).resolve().parent
STORE = HERE / "proprietary_store.json"
OUT = HERE / "export"

DOCS = 4_000
EGRESS_USD_PER_GB = 0.09  # us-east-1 data transfer out, first tier
LINK_MBPS = 100


def make_store() -> dict:
    """A deliberately provider-shaped document store: opaque keys, column map,
    a vendor version stamp and a schema only the vendor's SDK understands."""
    source = "proprietary_store.json"
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))

    rows = []
    for i in range(DOCS):
        rows.append(
            {
                "pk": f"ACC#{i:05d}",
                "sk": "PROFILE",
                "cols": {
                    "holdername": f"Customer {i:05d}",
                    "msisdn": f"+2547{i:07d}",
                    "balancecents": (i * 7919) % 5_000_00,
                    "kyc": "verified" if i % 11 else "pending",
                    "opened": f"20{10 + (i % 14):02d}-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}",
                },
            }
        )
    store = {
        "_v": "AcmeNoSQL/2.1",
        "_export": "vendor SDK required for full fidelity",
        "table": "accounts",
        "rows": rows,
    }
    STORE.write_text(json.dumps(store, indent=1), encoding="utf-8")
    return store


def digest(records: list[dict]) -> str:
    """SHA-256 over the canonical form of every business field, in key order."""
    h = hashlib.sha256()
    for r in records:
        h.update(json.dumps(r, sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()


def main() -> int:
    OUT.mkdir(exist_ok=True)
    store = make_store()
    started = time.perf_counter()

    print(f"source   {STORE.name} · {store['_v']} · table '{store['table']}'")
    print(f"         {len(store['rows'])} documents, provider-specific shape (pk/sk/cols)\n")

    # 1. normalise out of the proprietary shape
    records = [
        {
            "account_id": doc["pk"].split("#", 1)[1],
            **{k: v for k, v in doc["cols"].items()},
        }
        for doc in store["rows"]
    ]
    records.sort(key=lambda r: r["account_id"])

    # 2. write three open artefacts
    ok = {}
    with (OUT / "accounts.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    (OUT / "accounts.json").write_text(json.dumps(records, indent=1) + "\n", encoding="utf-8")

    db = OUT / "accounts.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE accounts (account_id TEXT PRIMARY KEY, holdername TEXT, msisdn TEXT, "
        "balancecents INTEGER, kyc TEXT, opened TEXT)"
    )
    con.executemany(
        "INSERT INTO accounts VALUES (:account_id,:holdername,:msisdn,:balancecents,:kyc,:opened)",
        records,
    )
    con.commit()

    # 3. verify completeness and fidelity, property by property
    read_csv = [
        {k: (int(v) if k == "balancecents" else v) for k, v in row.items()}
        for row in csv.DictReader((OUT / "accounts.csv").open(encoding="utf-8"))
    ]
    read_json = json.loads((OUT / "accounts.json").read_text(encoding="utf-8"))
    read_db = [
        dict(zip(["account_id", "holdername", "msisdn", "balancecents", "kyc", "opened"], row))
        for row in con.execute("SELECT * FROM accounts ORDER BY account_id")
    ]
    con.close()

    expected = digest(records)
    printed = False
    for label, got in (("csv", read_csv), ("json", read_json), ("sqlite", read_db)):
        same = digest(got) == expected and len(got) == len(records)
        ok[label] = same
        if not printed:
            print(f"integrity  sha256 {expected[:32]}…")
            print(f"           every field of every record, canonical order\n")
            printed = True
        print(f"  {label:<7} {len(got):>5} records  {'match' if same else 'MISMATCH'}")

    elapsed = time.perf_counter() - started
    total_bytes = sum(p.stat().st_size for p in (OUT / "accounts.csv", OUT / "accounts.json", db))
    gb = total_bytes / 1024**3
    cost = gb * EGRESS_USD_PER_GB
    transfer_s = total_bytes * 8 / (LINK_MBPS * 1_000_000)

    print(f"\ntransfer")
    print(f"  exported     {total_bytes / 1024:,.1f} KiB in {elapsed * 1000:.0f} ms")
    print(f"  egress cost  ${cost:.6f} at ${EGRESS_USD_PER_GB:.2f}/GB (pre-2024 rates)")
    print(f"  with waiver  $0.00 — the 2024 exit-fee commitments cover this case")
    print(f"  over {LINK_MBPS} Mbps  {transfer_s:.2f} s of link time for this volume")

    complete = all(ok.values())
    print(f"\n{'exit rehearsal passed' if complete else 'EXIT REHEARSAL FAILED'} — "
          f"{len(records)} of {len(store['rows'])} records recovered in three open formats")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
