<div align="center">

# 05 · Private cloud with Eucalyptus

**The product was the API, not the hypervisor.** Eucalyptus is dead software with a live idea: implement
Amazon's API on hardware you own, and every AWS tool, script and skill works unchanged. This module takes
the architecture apart — five controllers, three levels — and then builds the part that mattered, because
the original cannot be installed any more.

![module](https://img.shields.io/badge/module-05%20of%2015-e36209?style=flat-square)
![lab](https://img.shields.io/badge/lab-EC2%20Query%20API%20on%20port%208773-1f6feb?style=flat-square)
![states](https://img.shields.io/badge/measured-pending%20%E2%86%92%20running%20in%201.21%20s-2ea043?style=flat-square)
![deps](https://img.shields.io/badge/dependencies-none-6e7781?style=flat-square)

[**Read the page →**](https://mmmmohammed.github.io/cloud-computing-security/module-05/) &nbsp;·&nbsp;
[← Module 04](../module-04/) &nbsp;·&nbsp;
[Portfolio](../)

</div>

---

## What this module demonstrates

| Skill | Evidence in this folder |
|---|---|
| **Designing against an API contract** | A 369-line control plane speaking the EC2 Query API — five actions, the real XML envelope, instance state transitions — on the port a real Cloud Controller uses. |
| **Authentication on the server side** | Every request is verified with the module 04 signer: 400 when unsigned, 403 when the secret is wrong. Generating a signature is easy; checking one is where the bugs live. |
| **Failure-domain reasoning** | A table of what survives the loss of each component, including the one that explains a real power cut: two clusters, two buildings, two blast radii. |
| **Judgement about legacy** | Eucalyptus was acquired by HP in 2014 and is now largely legacy. The page says so, then explains what is still worth learning from it. |

---

## What it builds on

| From | What came forward | Where it is used again |
|---|---|---|
| **Module 04** | Signature Version 4, written from the spec | Imported and used *server-side* to verify every request in the lab |
| **Module 03** | The responsibility matrix and deployment models | Why an organisation would run its own cloud, and what it now owns |
| **Module 01** | Failure as the normal case | The "what survives what" table, and polling instead of assuming |

---

## Check it in two minutes

| Look at | What it shows |
|---|---|
| [`labs/week05/minicloud.py`](../labs/week05/minicloud.py) | The control plane: five actions, XML, signature verification |
| [`labs/week05/euca_client.py`](../labs/week05/euca_client.py) | The lifecycle driver, plus the two deliberate refusals |
| [`labs/week05/euca_client.log`](../labs/week05/euca_client.log) | The captured run quoted on the page |
| [The page](https://mmmmohammed.github.io/cloud-computing-security/module-05/) | The five-controller explorer and the failure-domain table |

---

## What the page covers

| # | Section | What it argues |
|---|---|---|
| 01 | [What it was](https://mmmmohammed.github.io/cloud-computing-security/module-05/#what) | UCSB research, 2008, AWS-compatible APIs, acquired 2014, legacy now — and why it is still studied. |
| 02 | [Architecture](https://mmmmohammed.github.io/cloud-computing-security/module-05/#architecture) | CLC, Walrus, CC, SC, NC — each one's job, what breaks without it, and its AWS twin. |
| 03 | [Mapping](https://mmmmohammed.github.io/cloud-computing-security/module-05/#mapping) | EC2, S3, EBS, IAM, AMI → EMI + EKI + ERI, AZ → cluster. |
| 04 | [Life of a request](https://mmmmohammed.github.io/cloud-computing-security/module-05/#request) | Six hops from `euca-run-instances` to a running machine, with where each one fails. |
| 05 | [Querying](https://mmmmohammed.github.io/cloud-computing-security/module-05/#query) | euca2ools, then boto3 with `endpoint_url` — the flag that proved compatibility. |
| 06 | [Tools](https://mmmmohammed.github.io/cloud-computing-security/module-05/#tools) | ElasticFox and HybridFox died with the plugin runtime; the CLI did not. |
| 07 | [Failure domains](https://mmmmohammed.github.io/cloud-computing-security/module-05/#failures) | If this dies, what still works — six rows the diagram never shows. |
| 08 | [Nebula](https://mmmmohammed.github.io/cloud-computing-security/module-05/#nebula) | NASA outgrew it, wrote a compute controller, and started OpenStack in 2010. |
| 09 | [Securing both planes](https://mmmmohammed.github.io/cloud-computing-security/module-05/#security) | Control plane and data plane, five items each. |
| 10 | [Lab](https://mmmmohammed.github.io/cloud-computing-security/module-05/#lab) | The build, the output, and the two refusals. |
| 11 | [Kaunti Health](https://mmmmohammed.github.io/cloud-computing-security/module-05/#case) | A console on public Wi-Fi, shared admin credentials, one building dark. |

---

## The lab — why not the lab sheet's route

The sheet offers a Eucalyptus FastStart VM, or LocalStack as an AWS-compatible substitute.

- **FastStart** images are no longer distributed; the project was archived years ago.
- **LocalStack** needs Docker, and this machine has neither Docker nor Podman installed (`command -v` returns
  nothing for both).

So I built the thing the module is actually about. Not a mock, not a screenshot: a control plane.

### Run it

```bash
cd labs/week05
python3 euca_client.py     # starts the control plane, drives it, stops it
python3 minicloud.py       # or run the control plane on its own, port 8773
```

### What it does

```
$ python3 euca_client.py
private cloud up on http://127.0.0.1:8773/  · sigv4 verified server-side

1 · euca-describe-availability-zones verbose
    building-a   19 free of 24 · available
    building-b   12 free of 24 · available

2 · euca-describe-images
    emi-1A2B3C4D   ubuntu-22.04-lab       kernel eki-1A2B3C4D · ramdisk eri-1A2B3C4D
    emi-5E6F7A8B   debian-12-hardened     kernel eki-5E6F7A8B · ramdisk eri-5E6F7A8B

3 · euca-run-instances
    i-97ab27eb  emi-1A2B3C4D  building-a  m1.small  state=pending  ip=10.0.0.10  (1.3 ms)
    i-09d33829  emi-5E6F7A8B  building-b  m1.large  state=pending  ip=10.0.0.11  (1.0 ms)

4 · euca-describe-instances (one call, all instances)
    i-97ab27eb  pending → running  after 1.21 s
    i-09d33829  pending → running  after 1.21 s
    7 describe calls, 0.2 s apart — the poll is the API working as designed

5 · euca-terminate-instances
    i-97ab27eb  → 200  shutting-down
    i-09d33829  → 200  shutting-down

6 · refusals
    unsigned      → 400 MissingAuthenticationToken
    wrong secret  → 403 AuthFailure

summary
    launched      2 instances across 2 clusters
    reached       running in 1.21 s
    terminated    2/2
    refusals      400 unsigned · 403 wrong secret
    problems      none
```

### The two refusals

| Request | Status | Error code | Why it matters |
|---|---|---|---|
| Signed correctly | **200** | — | Same envelope, same signature, different cloud — compatibility in one line |
| No `Authorization` header | **400** | `MissingAuthenticationToken` | Refused before the scheduler is reached |
| Signed with the wrong secret | **403** | `AuthFailure` | Header parsed, signature compared, then refused — the tampering check |

### What this does not prove

It is **not Eucalyptus**, not a hypervisor, and not a private cloud anyone should run: the "instances" are
timed state transitions in memory. It proves the control plane is the interesting part, that I can build
one against a real API contract, and that I can *verify* signatures rather than only generate them. Real
hypervisor work is the next practical step, and the page says so where a reader will see it.

---

## How the page is built

- **The architecture explorer is a switcher, not decoration:** five buttons, five panels, `aria-pressed` on
  the active one, everything readable as plain text with JavaScript off.
- **One shared `switchPanels()`** drives both this page and module 04's signing stepper — the same component,
  used twice, rather than two copies of the same code.
- **Hand-written HTML and CSS**, one stylesheet and one script for the whole site. No framework, no build step.
- **Light and dark** through `prefers-color-scheme`; print stylesheet included.
- **No tracking, no cookies, no analytics.**

---

## Answer key

<details>
<summary>Five answers, so you can check yourself before clicking</summary>

| Question | Answer |
|---|---|
| 1 | C |
| 2 | A |
| 3 | D |
| 4 | A |
| 5 | C |

</details>

---

## Honest limits

- **The lab sheet's own route was not run** — no FastStart VM, no LocalStack — and the reason is mechanical,
  not a preference: the images are gone and Docker is not installed here.
- The control plane is a **compatibility demonstration**, not a product. No hypervisor, no real networking,
  no persistent volumes.
- Instance states are simulated with timers; the 1.21 s is a design choice, not a measurement of boot time.
- Eucalyptus itself is legacy. The architecture lessons transfer to OpenStack and to provider control
  planes, which is the claim the page actually makes.

---

## Files

```
module-05/
├── index.html          the page — 3,741 words, 48 KB, no runtime dependencies
└── README.md           this file

labs/week05/
├── minicloud.py        EC2 Query API, five actions, SigV4 verified per request
├── euca_client.py      signed client: zones, images, launch, poll, terminate, refusals
├── euca_client.log     captured run quoted on the page
└── mini_cloud.json     the same run, structured
```

---

<div align="center">

**[← Module 04](../module-04/)** &nbsp;·&nbsp; **[Portfolio](../)** &nbsp;·&nbsp; **[Read the page →](https://mmmmohammed.github.io/cloud-computing-security/module-05/)**

</div>
