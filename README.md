# cloud computing security

A working portfolio for cloud computing and cloud security: one module per topic, each turned into
something runnable and explained rather than a set of slides.

**Live:** https://mmmmohammed.github.io/cloud-computing-security/

## Modules

| # | Module | What is in it |
|---|--------|----------------|
| 01 | [Distributed Computing](module-01/index.html) | The six eras of computing, distributed-system properties and transparency, the eight fallacies, a socket lab that fails on purpose, and the SACCO case study quiz |
| 02 | [Cloud Fundamentals](module-02/index.html) | The NIST SP 800-145 definition, five characteristics paired with the risks they create, virtualisation and hypervisors, the launch pipeline, and a lab reading 42 AWS regions from public data |

## Module 01 — what this covers

Before securing a cloud you have to know what one is: a **distributed system** — independent computers
that appear to users as one coherent system. The page works through:

- **Six eras** — mainframes and time-sharing → PCs and client–server → internet and clusters → grid and utility → cloud → edge, serverless and AI. Centralised, decentralised, centralised again.
- **Six properties** — resource sharing, concurrency, scalability, fault tolerance, no global clock, transparency.
- **Six forms of transparency** — access, location, migration, replication, concurrency, failure — and what each one hides from you.
- **Three-tier architecture** — presentation, application, data, with the AWS service that usually fills each tier.
- **Five paradigms** — cluster, grid, utility, cloud, edge, compared on ownership and coupling.
- **Eight fallacies of distributed computing** — each with its security consequence.
- **The lab** — real latency measurements and a real `ConnectionRefusedError`, kept in the repo.

## The lab (`labs/week01/`)

```bash
cd labs/week01

# 1. Regional latency: TCP handshake to port 443, five samples per endpoint
python3 probe_regions.py

# 2. Socket server/client, then break it
python3 socket_server.py &          # terminal A
python3 socket_client_naive.py      # terminal B -> succeeds

kill %1                             # stop the server
python3 socket_client_naive.py      # -> ConnectionRefusedError, unhandled
python3 socket_client_retry.py      # -> retries, then recovers or gives up cleanly
```

### Results from this machine

| Endpoint | Min | Avg | Jitter |
|---|---|---|---|
| AWS af-south-1 · Cape Town | 80.4 ms | **83.5 ms** | 1.8 ms |
| AWS eu-west-1 · Ireland | 189.0 ms | 193.6 ms | 2.6 ms |
| AWS us-east-1 · N. Virginia | 212.4 ms | 217.1 ms | 4.7 ms |
| Azure · South Africa North | — | DNS resolution failed | — |

Cape Town is **2.3× faster** than Ireland from here. The gap is distance, not bandwidth — which is the
whole point of fallacy 02 ("latency is zero").

### What the failure taught

| Client | Behaviour when the server is gone |
|---|---|
| `socket_client_naive.py` | Unhandled `ConnectionRefusedError`, process dies |
| `socket_client_retry.py` | 3 attempts, 2 s deadline each, linear backoff — recovers when the server returns, gives up cleanly when it does not |

Only the client's assumptions changed. That is fault tolerance at the smallest possible scale, and the
same three lines (timeout, bounded attempts, backoff) are what stop an outage from turning into a retry
storm against an authentication service.

## Layout

```
index.html                 portfolio landing page, indexes the modules
module-01/index.html       module 01 — distributed computing
module-02/index.html       module 02 — cloud fundamentals
assets/css/styles.css      one design system, shared by every page
assets/js/main.js          contents rail, quiz, timing panel, sortable tables
labs/week01/               socket lab scripts, captured logs, latency JSON
labs/week02/               AWS region probe, dataset summary, captured output
```

## Run it locally

Open `index.html`, or serve it:

```bash
python3 -m http.server 8000
```

## Reading

- Tanenbaum & van Steen (2013), *Distributed Systems*, Ch. 1
- Coulouris et al. (2011), *Distributed Systems*, Ch. 1–2
- Buyya et al. (2011), *Cloud Computing: Principles and Paradigms*, Ch. 1
