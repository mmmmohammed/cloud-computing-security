<div align="center">

# 04 · Public cloud vendors, web services and APIs

**Every action in the cloud is one signed HTTP request.** Launching a server, deleting a backup, reading a
bucket — underneath, each is an API call with an identity attached. So this module does two things: it maps
the three big vendors against each other, and then implements the signature scheme that stands between an
attacker and everything that identity is allowed to do.

The signature implementation is not described here. It is **written from the specification, checked against
AWS's published test vector, and it exits non-zero when it disagrees**.

![module](https://img.shields.io/badge/module-04%20of%2015-6e40c9?style=flat-square)
![vector](https://img.shields.io/badge/SigV4-matches%20the%20AWS%20test%20vector-2ea043?style=flat-square)
![lab](https://img.shields.io/badge/lab-200%20%C2%B7%20400%20%C2%B7%20401%20measured-1f6feb?style=flat-square)
![deps](https://img.shields.io/badge/dependencies-none-6e7781?style=flat-square)

[**Read the page →**](https://mmmmohammed.github.io/cloud-computing-security/module-04/) &nbsp;·&nbsp;
[← Module 03](../module-03/) &nbsp;·&nbsp;
[Portfolio](../)

</div>

---

## What this module demonstrates

| Skill | Evidence in this folder |
|---|---|
| **Implementing a protocol from a specification** | Signature Version 4 in 145 lines of Python standard library — canonical request, string to sign, HMAC key chain — reproducing AWS's published `get-vanilla` signature byte for byte. |
| **Cross-vendor fluency** | Eight capabilities mapped across AWS, Azure and Google Cloud, plus the same three operational questions asked as `aws` / `az` / `gcloud` commands. |
| **Reading a provider's refusal** | Three real endpoints, three different answers: `200` for public data, `400 MissingParameter` before authentication, `401 AuthFailure` after it. |
| **Operational judgement** | Vendor selection as six questions — region, compliance, services, cost, exit, support — with the December 2021 `us-east-1` failure as the case for why availability is a security property. |

---

## What it builds on

The earlier modules are not background here; they are load-bearing. Three of them are reused directly.

| From | What came forward | Where it is used again |
|---|---|---|
| **Module 01** | The eight fallacies of distributed computing | Why every API call needs a timeout and its own authentication, not just TLS — section 03 |
| **Module 02** | Region counts and measured handshake latency | The vendor-selection table quotes Cape Town 84.8 ms against Ireland 159.3 ms — section 02 |
| **Module 03** | The seven-layer responsibility matrix | Explains why the identity row never moves to the provider, and why a stolen key is *your* breach — sections 01 and 04 |

---

## Check it in two minutes

| Look at | What it shows |
|---|---|
| [`labs/week04/sigv4.py`](../labs/week04/sigv4.py) | The whole signing algorithm, no SDK, no account |
| [`labs/week04/sigv4_check.log`](../labs/week04/sigv4_check.log) | Every intermediate value and the published expected signature |
| [`labs/week04/api_probe.log`](../labs/week04/api_probe.log) | Three real AWS endpoints refusing three different ways |
| [The page](https://mmmmohammed.github.io/cloud-computing-security/module-04/) | The five-step stepper built from those actual computed values |

---

## What the page covers

| # | Section | What it argues |
|---|---|---|
| 01 | [Vendors](https://mmmmohammed.github.io/cloud-computing-security/module-04/#vendors) | Same eight primitives, three sets of names; the mapping is not one-to-one, which is where migrations hurt. |
| 02 | [Choosing](https://mmmmohammed.github.io/cloud-computing-security/module-04/#choose) | Six criteria, one of them legal, and what they look like from Kenya. |
| 03 | [Web services](https://mmmmohammed.github.io/cloud-computing-security/module-04/#webservices) | SOAP vs REST, JSON vs XML, and the status codes that make 401 and 403 different investigations. |
| 04 | [Signing](https://mmmmohammed.github.io/cloud-computing-security/module-04/#auth) | Five steps with the real computed values — and what signing does **not** protect. |
| 05 | [CLIs and SDKs](https://mmmmohammed.github.io/cloud-computing-security/module-04/#cli) | The same questions on three clouds; why "who am I" comes first. |
| 06 | [Standards](https://mmmmohammed.github.io/cloud-computing-security/module-04/#standards) | Six families, and the difference between a checklist and a management system. |
| 07 | [The outage](https://mmmmohammed.github.io/cloud-computing-security/module-04/#outage) | `us-east-1`, 7 December 2021 — and 14% of AWS's prefixes sitting in one region. |
| 08 | [Pwani Logistics](https://mmmmohammed.github.io/cloud-computing-security/module-04/#case) | A key on a shared drive, ranked against a slow system. |
| 09 | [The lab](https://mmmmohammed.github.io/cloud-computing-security/module-04/#lab) | The account half marked not run; the signature half verified. |
| 10 | [Quiz](https://mmmmohammed.github.io/cloud-computing-security/module-04/#quiz) | Five questions on the Pwani case. |

---

## The lab — sign a request, then get refused three ways

The lab sheet asks for AWS CLI v2 with a Learner Lab account, boto3, an `AccessDenied`, and matching
CloudTrail events. **That half is not run** — no account — and the page says so where a reader will see it.

The half that proves the mechanism needs no account at all.

### 1. The signature, from the specification

```bash
cd labs/week04
python3 sigv4.py        # exits 0 only if it matches AWS's published vector
```

```text
step 1 · canonical request
    GET
    /

    host:example.amazonaws.com
    x-amz-date:20150830T123600Z

    host;x-amz-date
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

step 2 · string to sign
    AWS4-HMAC-SHA256
    20150830T123600Z
    20150830/us-east-1/service/aws4_request
    bb579772317eb040ac9ed261061d46c1f17a8133879d6129b6e1c25292927e63

step 3 · signing key (HMAC chain, hex)
    938127b5336810ddb6a5d6af445fcac9e371f9ed418ed386b022aed82901be75

step 4 · signature
    5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31

MATCH — implementation agrees with the published vector
```

Why this counts as evidence rather than a demo: the expected signature is a **fixed constant published by
AWS**. Getting it right requires the canonical request, the string to sign and the HMAC key chain all to be
correct at once. Getting it wrong is silent — so the script asserts, and fails loudly.

### 2. Three ways to be told no

```bash
python3 api_probe.py    # read-only calls, AWS's documented example credentials
```

| Request | Status | Error code | What it means |
|---|---|---|---|
| `ip-ranges.amazonaws.com`, unsigned | **200** | — | Public data; 2.7 MB returned with no identity at all |
| `ec2` DescribeRegions, unsigned | **400** | `MissingParameter` | Rejected at parameter validation, before authentication |
| `ec2` DescribeRegions, signed with the example key | **401** | `AuthFailure` | Header parsed, credentials evaluated, then refused |

The useful row is the third. `400` means the service could not read the request; `401` means it read it,
understood it, and refused on identity. In triage, a wall of 401s from one source IP is a credential problem
worth chasing; a wall of 400s is usually a broken client.

### What this lab does not prove

It does not prove I can operate a cloud account — the CLI, boto3 and CloudTrail sequence is still
unexercised, and the page says so. What it does prove is that I can read a cryptographic specification,
implement it against a published vector, and interpret a provider's error responses. Different skills, kept
separate on purpose.

---

## How the page is built

- **The stepper in section 04 shows computed values, not illustrations.** Every hash and signature in those
  five panels came out of `sigv4.py`; the expected value is AWS's.
- **Hand-written HTML and CSS**, sharing one stylesheet and one script with modules 01–03. No framework, no
  build step.
- **Accessible interaction:** stepper buttons carry `aria-pressed`, panels toggle `hidden`, and all five
  steps are ordinary text a reader can select and compare by eye.
- **Light and dark** through `prefers-color-scheme`; print stylesheet included.
- **No tracking, no cookies, no analytics.**

---

## Answer key

<details>
<summary>Five answers, so you can check yourself before clicking</summary>

| Question | Answer |
|---|---|
| 1 | B |
| 2 | C |
| 3 | B |
| 4 | D |
| 5 | C |

</details>

---

## Honest limits

- **The account half was not run:** no CLI session, no boto3 listing, no `AccessDenied` of my own, no
  CloudTrail screenshots. Stated on the page, in the lab section.
- **The signature proves the algorithm, not the account.** Matching AWS's vector says nothing about whether
  I can operate a real environment — that is the next practical step.
- The probe used AWS's **published example** key pair. No real credentials were created, stored or sent
  anywhere, and every call was read-only.
- Measurements are from one machine on one day: the public payload was 2.7 MB and the timings will differ on
  every run.

---

## Files

```
module-04/
├── index.html          the page — 3,484 words, 46 KB, no runtime dependencies
└── README.md           this file

labs/week04/
├── sigv4.py            SigV4 from the spec + assertion against AWS's test vector
├── sigv4_check.log     captured run: every intermediate value
├── api_probe.py        three real endpoints, three refusal modes
├── api_probe.log       captured console output
└── api_probe.json      the same results, structured
```

---

<div align="center">

**[← Module 03](../module-03/)** &nbsp;·&nbsp; **[Portfolio](../)** &nbsp;·&nbsp; **[Read the page →](https://mmmmohammed.github.io/cloud-computing-security/module-04/)**

</div>
