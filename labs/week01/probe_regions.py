"""Week 1 lab: measure TCP handshake latency to cloud endpoints in different regions."""
import socket, statistics, time, json

TARGETS = [
    ("AWS af-south-1 (Cape Town)", "s3.af-south-1.amazonaws.com"),
    ("AWS eu-west-1 (Ireland)", "s3.eu-west-1.amazonaws.com"),
    ("AWS us-east-1 (N. Virginia)", "s3.us-east-1.amazonaws.com"),
    ("Azure (South Africa North)", "zaosoutheast.blob.core.windows.net"),
]

results = []
for label, host in TARGETS:
    samples, last_err = [], None
    try:
        ip = socket.gethostbyname(host)
    except OSError as e:
        print(f"{label:34s} DNS FAILED: {e!r}")
        continue
    for _ in range(5):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        t0 = time.perf_counter()
        try:
            s.connect((ip, 443))
            samples.append((time.perf_counter() - t0) * 1000)
        except OSError as e:
            last_err = e
        finally:
            s.close()
        time.sleep(0.2)
    if samples:
        results.append({
            "target": label, "host": host, "ip": ip,
            "min_ms": round(min(samples), 1),
            "avg_ms": round(statistics.mean(samples), 1),
            "jitter_ms": round(statistics.pstdev(samples), 1),
        })
        r = results[-1]
        print(f"{label:34s} {ip:16s} min={r['min_ms']:7.1f}ms avg={r['avg_ms']:7.1f}ms")
    else:
        print(f"{label:34s} ALL CONNECTIONS FAILED: {last_err!r}")

with open("region_latency.json", "w") as f:
    json.dump(results, f, indent=2)
