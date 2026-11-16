"""Week 2 lab, measurable half.

1. Reads AWS's public ip-ranges.json (no credentials) to list every region it
   publishes, and counts how many service prefixes each one has.
2. Measures the TCP handshake to the S3 endpoint of five regions from here.
3. Writes week02_regions.json for the module page.
"""
import json
import os
import socket
import statistics
import time
import urllib.request

IP_RANGES = "https://ip-ranges.amazonaws.com/ip-ranges.json"
CACHE = "ip-ranges.json"
ENDPOINTS = [
    ("af-south-1", "Cape Town", "s3.af-south-1.amazonaws.com"),
    ("me-south-1", "Bahrain", "s3.me-south-1.amazonaws.com"),
    ("ap-south-1", "Mumbai", "s3.ap-south-1.amazonaws.com"),
    ("eu-west-1", "Ireland", "s3.eu-west-1.amazonaws.com"),
    ("us-east-1", "N. Virginia", "s3.us-east-1.amazonaws.com"),
]

if os.path.exists(CACHE):
    raw = open(CACHE, "rb").read()
else:
    raw = urllib.request.urlopen(IP_RANGES, timeout=45).read()
    open(CACHE, "wb").write(raw)

data = json.loads(raw)
published = sorted({p["region"] for p in data["prefixes"] if p.get("region") and p["region"] != "GLOBAL"})
per_region = {}
for p in data["prefixes"]:
    r = p.get("region")
    if r and r != "GLOBAL":
        per_region[r] = per_region.get(r, 0) + 1

print(f"ip-ranges.json: {len(raw)/1e6:.1f} MB, {len(data['prefixes'])} prefixes, "
      f"sync token {data['syncToken']}, published {data['createDate']}")
print(f"regions published by AWS: {len(published)}")

measured = []
for code, city, host in ENDPOINTS:
    try:
        ip = socket.gethostbyname(host)
    except OSError as e:
        print(f"{code:12s} DNS FAILED {e!r}")
        continue
    samples = []
    for _ in range(5):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        t0 = time.perf_counter()
        try:
            s.connect((ip, 443))
            samples.append((time.perf_counter() - t0) * 1000)
        except OSError:
            pass
        finally:
            s.close()
        time.sleep(0.15)
    if samples:
        measured.append({
            "region": code, "city": city, "ip": ip,
            "min_ms": round(min(samples), 1),
            "avg_ms": round(statistics.mean(samples), 1),
            "prefixes": per_region.get(code, 0),
        })
        print(f"{code:12s} {city:13s} {ip:16s} avg {measured[-1]['avg_ms']:7.1f} ms   "
              f"{per_region.get(code, 0):4d} prefixes")
    else:
        print(f"{code:12s} {city:13s} no handshake")

out = {
    "source": IP_RANGES,
    "published_regions": len(published),
    "prefixes": len(data["prefixes"]),
    "sync_token": data["syncToken"],
    "measured": measured,
}
json.dump(out, open("week02_regions.json", "w"), indent=2)
print(f"\nwrote week02_regions.json ({len(measured)} regions measured)")
