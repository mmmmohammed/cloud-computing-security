<div align="center">

# 01 · Distributed computing

**A cloud is a distributed system before it is anything else.** This module is that claim at the smallest possible scale: a socket client I broke on purpose, latency I measured to three regions from one machine, and the eight fallacies of distributed computing each tied to a way an attacker gets in.

![module](https://img.shields.io/badge/module-01%20of%2015-1f6feb?style=flat-square)
![stack](https://img.shields.io/badge/hand%20written-HTML%20%26%20CSS-9a3412?style=flat-square)
![lab](https://img.shields.io/badge/lab-real%20output%20in%20the%20repo-2ea043?style=flat-square)
![deps](https://img.shields.io/badge/dependencies-none-6e7781?style=flat-square)

[**Read the page →**](https://mmmmohammed.github.io/cloud-computing-security/module-01/) &nbsp;·&nbsp;
[Portfolio](../) &nbsp;·&nbsp;
[Module 02 →](../module-02/)

</div>

---

## What this module demonstrates

| Skill | Evidence in this folder |
|---|---|
| **Systems reasoning** | Six eras of computing, six properties of distributed systems, and five paradigms compared on ownership and coupling — not definitions copied, but a model that predicts why cloud won. |
| **Failure analysis** | A client that is logically correct and still dies, with the traceback kept. Then the same client fixed with a timeout, bounded retries and backoff. |
| **Measurement over assertion** | TCP handshake latency to three AWS regions, five samples each, jitter reported. The number that matters is the 2.3× gap between Cape Town and Ireland. |
| **Security framing** | Every one of the eight fallacies is paired with its security consequence — "the network is reliable" becomes a dropped session, "topology doesn't change" becomes an unrotated certificate. |

---

## Check it in two minutes

| Look at | What it shows |
|---|---|
| [The page](https://mmmmohammed.github.io/cloud-computing-security/module-01/) | Structured argument, designed typography, dark mode, print stylesheet |
| [`labs/week01/client_crash.log`](../labs/week01/client_crash.log) | The unhandled `ConnectionRefusedError`, exactly as it happened |
| [`labs/week01/socket_client_retry.py`](../labs/week01/socket_client_retry.py) | 17 lines: deadline, three attempts, linear backoff, clean exit |
| [`labs/week01/region_latency.json`](../labs/week01/region_latency.json) | The raw numbers behind every latency claim on the page |

---

## What the page covers

| # | Section | What it argues |
|---|---|---|
| 01 | [Eras](https://mmmmohammed.github.io/cloud-computing-security/module-01/#eras) | Computing swings between centralised and distributed; each swing changes who owns the security. |
| 02 | [A distributed system](https://mmmmohammed.github.io/cloud-computing-security/module-01/#system) | Independent machines that appear as one — and what "appear" costs you. |
| 03 | [Transparency](https://mmmmohammed.github.io/cloud-computing-security/module-01/#transparency) | Six kinds of transparency; each one is a convenience for the user and a blind spot for the operator. |
| 04 | [Three tiers](https://mmmmohammed.github.io/cloud-computing-security/module-01/#architecture) | Presentation, application, data — three attack surfaces, mapped to the AWS service that usually fills each. |
| 05 | [Paradigms](https://mmmmohammed.github.io/cloud-computing-security/module-01/#paradigms) | Cluster, grid, utility, cloud, edge, compared on ownership and coupling. |
| 06 | [Eight fallacies](https://mmmmohammed.github.io/cloud-computing-security/module-01/#fallacies) | Each false assumption, the failure it causes, and the security consequence. |
| 07 | [Netflix](https://mmmmohammed.github.io/cloud-computing-security/module-01/#case) | A real migration driven by one database's limits. |
| 08 | [Pipeline](https://mmmmohammed.github.io/cloud-computing-security/module-01/#pipeline) | Five steps from distributed computing to cloud. |
| 09 | [The lab](https://mmmmohammed.github.io/cloud-computing-security/module-01/#lab) | Latency measured, client broken, failure tamed. |
| 10 | [Quiz](https://mmmmohammed.github.io/cloud-computing-security/module-01/#quiz) | Five questions on the SACCO case — instant feedback, keyboard accessible. |

---

## The lab — measure it, then break it

Everything in `labs/week01/` was actually run on a Kali VM. The `.log` files are the captured output,
including the failures. Nothing here is reconstructed after the fact.

### 1. Latency is not zero

```bash
cd labs/week01
python3 probe_regions.py
```

Five TCP handshakes to port 443 per endpoint. No ICMP, no HTTP — the handshake alone, so the number is
network and nothing else.

| Endpoint | Min | Avg | Jitter |
|---|---|---|---|
| AWS `af-south-1` · Cape Town | 80.4 ms | **83.5 ms** | 1.8 ms |
| AWS `eu-west-1` · Ireland | 189.0 ms | **193.6 ms** | 2.6 ms |
| AWS `us-east-1` · N. Virginia | 212.4 ms | **217.1 ms** | 4.7 ms |
| Azure · South Africa North | — | DNS resolution failed | — |

**Cape Town is 2.3× faster than Ireland from the same laptop.** Nothing about bandwidth explains that.
It is distance plus queueing on a fixed path — fallacy 02, measured.

The Azure row is the most useful one: DNS failed, so there was no handshake to time.
Name resolution is the first availability dependency in any distributed system, and an easy one to
attack or misconfigure.

### 2. A correct program that still dies

```bash
python3 socket_server.py &        # terminal A
python3 socket_client_naive.py    # terminal B → ACK received
kill %1                           # stop the server
python3 socket_client_naive.py    # → ConnectionRefusedError, unhandled
python3 socket_client_retry.py    # 3 attempts, 2 s deadline, linear backoff
```

| Client | Behaviour when the server is gone |
|---|---|
| `socket_client_naive.py` | Unhandled `ConnectionRefusedError`, process dies |
| `socket_client_retry.py` | Attempts 1–2 fail, attempt 3 succeeds once the server returns; exits cleanly after three attempts if it does not |

Only the client's assumptions changed. That is fault tolerance and resilience engineering at the
smallest scale — and the same three ideas (deadline, bounded attempts, backoff) are what stop a
dependency outage from turning into a retry storm against an authentication service.

### 3. What a security reviewer should take from it

- **Unbounded retries are a self-inflicted denial of service.** Bounded failure is a feature.
- **A silent failure spends the most time undiagnosed.** The crash was better than a hang.
- **Transparency is selective.** `connect()` did not care whether the peer was local or remote — access
  transparency existed. Nothing masked the outage — failure transparency did not.

---

## How the page is built

- **Hand-written HTML and CSS.** No framework, no build step, no bundler — one shared stylesheet
  (`../assets/css/styles.css`) and one shared script (`../assets/js/main.js`) serve all three modules.
- **Accessibility:** semantic landmarks, a skip link, a contents rail with scroll-spy, `aria-pressed`
  and `aria-live` on interactive parts, visible focus states, quiz inputs locked after answering so the
  result cannot be changed by accident.
- **Light and dark** through `prefers-color-scheme`, with a print stylesheet that drops the chrome.
- **No tracking, no cookies, no analytics.** The only third-party request is Google Fonts.

---

## Answer key

<details>
<summary>Five answers, so you can check yourself before clicking</summary>

| Question | Answer |
|---|---|
| 1 | B |
| 2 | A |
| 3 | D |
| 4 | A |
| 5 | D |

</details>

---

## Honest limits

- The latency numbers describe **this machine on this connection, on the day it ran**. They are a
  demonstration of distance, not a benchmark of AWS regions.
- No cloud account was used anywhere in this module, so there is no console evidence to show — the lab
  is deliberately built from things that need nothing but Python and a network.
- The Azure endpoint was unreachable and is reported as unreachable rather than quietly dropped.

---

## Files

```
module-01/
├── index.html          the page — 2,656 words, 48 KB, no dependencies at build or run time
└── README.md           this file

labs/week01/
├── probe_regions.py            handshake latency, five samples, writes JSON
├── socket_server.py            minimal TCP server, replies ACK:<payload>
├── socket_client_naive.py      no timeout, no retry — the deliberate mistake
├── socket_client_retry.py      2 s deadline, three attempts, linear backoff
├── region_latency.json         raw measurements used on the page
└── *.log                       captured runs: success, crash, retry-fail, retry-recover
```

---

<div align="center">

**[← Portfolio](../)** &nbsp;·&nbsp; **[Module 02 · Cloud fundamentals →](../module-02/)**

</div>
