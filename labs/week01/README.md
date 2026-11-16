# Week 1 lab — Exploring a distributed system

Everything here was actually run; the `.log` files are the captured output, including the failures.

| File | Purpose |
|---|---|
| `probe_regions.py` | TCP handshake latency to cloud endpoints in three regions, 5 samples each, writes `region_latency.json` |
| `socket_server.py` | Minimal TCP server: accepts one connection, replies `ACK:<payload>` |
| `socket_client_naive.py` | Client with **no** timeout and **no** retry — the deliberate mistake |
| `socket_client_retry.py` | Client with a 2 s deadline, 3 attempts and linear backoff |
| `latency_run.log` | Console output of the latency probe |
| `client_success.log` | Happy path: server up, reply received |
| `client_crash.log` | Server stopped mid-session → unhandled `ConnectionRefusedError` |
| `client_retry_fail.log` | Retries exhausted against a server that never returns |
| `client_retry_recover.log` | Retry succeeds once the server comes back |
| `server_ok.log`, `server_ok2.log` | Server-side view of both successful requests |

## Run order

```bash
python3 probe_regions.py                                    # latency table

python3 socket_server.py &                                  # terminal A
python3 socket_client_naive.py                              # terminal B - succeeds
kill %1

python3 socket_client_naive.py                              # dies with ConnectionRefusedError
python3 socket_client_retry.py                              # retries, then recovers or gives up cleanly
```

## Observations

1. **Distance dominates latency.** Cape Town 83.5 ms vs Ireland 193.6 ms from the same machine, with
   tight jitter (1.8–4.7 ms). Nothing about bandwidth explains it: the RTT is the speed of light
   plus queueing on a fixed path.
2. **A correct program still crashed.** The naive client was logically correct and still died, because it
   assumed something that is not true: that the peer is still there.
3. **Retries change the failure mode, not the world.** Attempts 1 and 2 failed; attempt 3 succeeded
   because the server had restarted underneath — no code on the server side changed.
4. **Bounded failure is a feature.** With no server at all, the retry client exits cleanly after three
   attempts instead of hanging. Unbounded retry is how one dead dependency becomes a self-inflicted DoS.
5. **The Azure row never got a chance.** DNS failed, so there was no TCP handshake to time. Name
   resolution is the first availability dependency in any distributed system — and an easy one to
   attack or misconfigure.
6. **Transparency that existed:** access transparency (`connect()` does not care whether the peer is
   local or remote). **Missing:** failure transparency (nothing masked the outage) and relocation
   (there was no replica to move the request to).
