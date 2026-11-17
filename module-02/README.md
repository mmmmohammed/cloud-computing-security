<div align="center">

# 02 · Cloud fundamentals

**The NIST definition is a test you can fail.** Five characteristics, three service models, four
deployments — then the part most write-ups skip: what each characteristic quietly costs you in security,
and what actually happens between clicking *Launch instance* and getting a running machine. The lab reads
AWS's own published region data and measures handshakes to four of those regions.

![module](https://img.shields.io/badge/module-02%20of%2015-2ea043?style=flat-square)
![lab](https://img.shields.io/badge/data-42%20regions%20%C2%B7%2010%2C755%20prefixes-1f6feb?style=flat-square)
![measured](https://img.shields.io/badge/measured-4%20regions%20by%20handshake-9a3412?style=flat-square)
![deps](https://img.shields.io/badge/dependencies-none-6e7781?style=flat-square)

[**Read the page →**](https://mmmmohammed.github.io/cloud-computing-security/module-02/) &nbsp;·&nbsp;
[← Module 01](../module-01/) &nbsp;·&nbsp;
[Module 03 →](../module-03/)

</div>

---

## What this module demonstrates

| Skill | Evidence in this folder |
|---|---|
| **Reading a standard properly** | NIST SP 800-145 taken apart clause by clause, with a table of what *excludes* a system from being cloud — so the definition becomes a checklist, not a slogan. |
| **Threat modelling from first principles** | Each of the five essential characteristics is paired with the risk it creates: multi-tenancy → noisy neighbours and side channels, on-demand self-service → shadow IT, measured service → metering as an attack surface. |
| **Working with real published data** | `ip-ranges.json` from AWS: 2.8 MB, 10,755 prefixes, 42 regions — parsed and summarised, not quoted from a blog. |
| **Knowing the machine you are testing on** | The hypervisor facts of the VM this was written in, so "virtualisation" is not abstract. |

---

## Check it in two minutes

| Look at | What it shows |
|---|---|
| [The page](https://mmmmohammed.github.io/cloud-computing-security/module-02/) | A sortable regions table and the five-characteristics/risk pairing |
| [`labs/week02/regions_probe.py`](../labs/week02/regions_probe.py) | 83 lines: download, parse, summarise, handshake timings, JSON out |
| [`labs/week02/week02_regions.json`](../labs/week02/week02_regions.json) | The dataset the page's table is generated from |
| [`labs/week02/regions_run.log`](../labs/week02/regions_run.log) | The run that produced it |

---

## What the page covers

| # | Section | What it argues |
|---|---|---|
| 01 | [The definition](https://mmmmohammed.github.io/cloud-computing-security/module-02/#definition) | NIST 5-3-4, and a table of systems that look like cloud and are not. |
| 02 | [Five characteristics](https://mmmmohammed.github.io/cloud-computing-security/module-02/#characteristics) | Each one with the risk it creates — the argument the module is built on. |
| 03 | [Virtualisation](https://mmmmohammed.github.io/cloud-computing-security/module-02/#virtualisation) | Type 1 vs Type 2 hypervisors, the isolation boundary, and which one this machine is running inside. |
| 04 | [The launch pipeline](https://mmmmohammed.github.io/cloud-computing-security/module-02/#launch) | Five steps from a click to a running instance, and where each step is a security decision. |
| 05 | [Cloud vs traditional IT](https://mmmmohammed.github.io/cloud-computing-security/module-02/#compare) | Compared only on the factors that actually differ — not a feature list. |
| 06 | [Benefits and risks](https://mmmmohammed.github.io/cloud-computing-security/module-02/#ledger) | A ledger: every benefit on the left, the risk it arrives with on the right. |
| 07 | [Pokémon GO](https://mmmmohammed.github.io/cloud-computing-security/module-02/#case) | Elasticity under a 50× load spike, in real numbers. |
| 08 | [Where this is normal](https://mmmmohammed.github.io/cloud-computing-security/module-02/#uses) | Everyday systems people already depend on. |
| 09 | [The lab](https://mmmmohammed.github.io/cloud-computing-security/module-02/#lab) | Regions, handshakes, and the hypervisor I am inside. |
| 10 | [Quiz](https://mmmmohammed.github.io/cloud-computing-security/module-02/#quiz) | Five questions on the Duka Online case. |

---

## The lab — 42 regions, four handshakes

### Run it

```bash
cd labs/week02
python3 regions_probe.py
```

The script downloads `https://ip-ranges.amazonaws.com/ip-ranges.json` (public, no key, no account),
counts what is in it, then times a TCP handshake to an S3 endpoint in each region it measures. It writes
`week02_regions.json`; the page's table is built from that file.

`ip-ranges.json` is 2.8 MB and is git-ignored — the script re-downloads it, so the repo stays small and
the numbers stay reproducible.

### What it found

| Measure | Result |
|---|---|
| Payload | 2.8 MB, `syncToken 1794807425` |
| Published regions | **42** |
| IPv4 + IPv6 prefixes | **10,755** |

| Region | City | Handshake (avg) | Prefixes that region owns |
|---|---|---|---|
| `af-south-1` | Cape Town | **84.8 ms** | 139 |
| `ap-south-1` | Mumbai | **145.5 ms** | 304 |
| `eu-west-1` | Ireland | **159.3 ms** | 535 |
| `us-east-1` | N. Virginia | **216.6 ms** | 1,506 |
| `me-south-1` | Bahrain | no handshake completed | — |

### What the numbers mean

- **Region choice is a latency decision you can measure in a minute** — before you provision anything.
  Cape Town answers 2.5× faster than N. Virginia from here.
- **Ownership is concentrated.** One region (`us-east-1`) owns 1,506 of 10,755 prefixes — 14% of AWS's
  advertised address space. That is a fact about blast radius, and it is free to look up.
- **`me-south-1` did not answer.** Reported as not answering rather than removed, because "the endpoint
  was unreachable when I tested" is information, not noise.
- **The same file is what an allow-list is built from.** `ip-ranges.json` is how you write a firewall rule
  that follows AWS instead of hard-coding a range that rots.

---

## How the page is built

- **Hand-written HTML and CSS**, sharing one stylesheet and one script with modules 01 and 03. No
  framework, no build step.
- **The regions table is sortable** on every column, keyboard operable, and marks its sort direction with
  `aria-sort` — the data is real, so the table has to behave like data.
- **Light and dark** through `prefers-color-scheme`; print stylesheet included.
- **No tracking, no cookies, no analytics.**

---

## Answer key

<details>
<summary>Five answers, so you can check yourself before clicking</summary>

| Question | Answer |
|---|---|
| 1 | D |
| 2 | A |
| 3 | D |
| 4 | B |
| 5 | D |

</details>

---

## Honest limits

- **The account half of this lab was not run.** Creating an AWS account, turning on MFA, setting a
  billing alarm, launching EC2, deploying to Elastic Beanstalk and reading CloudTrail all need an account
  I do not have. The page says so, next to the part I did run, instead of describing console screenshots
  that do not exist.
- Latency figures describe this machine and this connection on the day of the run.
- The region count is a snapshot: AWS adds regions, and re-running the script will show a different number.

---

## Files

```
module-02/
├── index.html          the page — 3,014 words, 46 KB, no runtime dependencies
└── README.md           this file

labs/week02/
├── regions_probe.py        download, parse, summarise, measure, write JSON
├── week02_regions.json     the numbers the page is built from
└── regions_run.log         captured run
```

---

<div align="center">

**[← Module 01](../module-01/)** &nbsp;·&nbsp; **[Portfolio](../)** &nbsp;·&nbsp; **[Module 03 · Service and deployment models →](../module-03/)**

</div>
