<div align="center">

# 08 · Identity and access management with AWS IAM

**Identity is the cloud perimeter.** There is no office door to lock — anyone with valid credentials can reach
the console or the API from anywhere. This module implements AWS's documented policy evaluation order as a
working engine, checks it against 24 cases, then audits the deck's case-study account and takes it from
fourteen findings to zero.

![module](https://img.shields.io/badge/module-08%20of%2015-d1243a?style=flat-square)
![decisions](https://img.shields.io/badge/policy%20decisions-24%2F24-1f6feb?style=flat-square)
![audit](https://img.shields.io/badge/audit-14%20findings%20%E2%86%92%200-2ea043?style=flat-square)
![deps](https://img.shields.io/badge/dependencies-none-6e7781?style=flat-square)

[**Read the page →**](https://mmmmohammed.github.io/cloud-computing-security/module-08/) &nbsp;·&nbsp;
[← Module 07](../module-07/) &nbsp;·&nbsp;
[Portfolio](../)

</div>

---

## What this module demonstrates

| Skill | Evidence in this folder |
|---|---|
| **Reading the evaluation order as an algorithm** | `iam_eval.py` implements all six documented steps — explicit deny first, then SCP and boundary guardrails, then allow, then implicit deny. |
| **Writing policies that are actually least-privilege** | Wildcards, `NotAction`, resource policies with `Principal`, policy variables, and the condition operators a review uses. |
| **Testing policy decisions** | 24 cases with expected outcomes: deny precedence, region guardrails, boundary narrower than the policy, MFA and IP conditions, ABAC tag comparison, cross-account resource policy. |
| **Auditing an account** | A credential report, key-age and MFA checks, a least-privilege diff, and nine documented privilege-escalation paths detected by policy rather than by eye. |

---

## What it builds on

| From | What came forward | Where it reappears |
|---|---|---|
| **Module 07** | Data accountability never moves to the provider | Why “we are certified” does not cover your identities |
| **Module 06** | Hardening as a checklist you run | The policy gate becomes a policy *evaluator* |
| **Module 05** | A control plane is a set of decisions | Every IAM request is one decision with a documented order |

---

## The numbers

| Measure | Result |
|---|---|
| Evaluation cases | **24**, all matching the expected decision |
| Engine coverage | identity, resource, boundary and SCP policies; wildcards; `NotAction`; `Principal`; 7 condition operators; policy variables |
| Tumaini audit | **14 findings** — 3 critical, 7 high, 4 medium |
| Escalation paths in one admin group | **9** documented pairs, detected from the policy set |
| Least-privilege rewrite | `s3:*` on `*` → **`s3:PutObject`** on `arn:aws:s3:::loan-docs/*` |
| After remediation | **0 findings** in the fixed model |

---

## Check it in two minutes

| Look at | What it shows |
|---|---|
| [`labs/week08/cases.json`](../labs/week08/cases.json) | Every case: request, policies, expected decision |
| [`labs/week08/iam_eval.py`](../labs/week08/iam_eval.py) | The six-step evaluator and the `--explain` trace |
| [`labs/week08/access_review.py`](../labs/week08/access_review.py) | Credential report, findings, escalation scan, remediation |
| [`labs/week08/access_review.log`](../labs/week08/access_review.log) | The captured audit, quoted on the page |

---

## Run it

```bash
cd labs/week08

python3 iam_eval.py --test                 # 24 cases, checks every decision
python3 iam_eval.py --explain "explicit"   # trace one request through the six steps
python3 access_review.py                   # credential report + findings
python3 access_review.py --fix             # apply the remediation to the model and re-audit
```

Requirements: Python 3 only. No packages, no account, no network.

---

## What was and was not done

**Run:** the evaluator against 24 cases, the traced decisions, the credential report, the escalation scan, the
least-privilege diff, and a remediation that re-audits to zero findings.

**Not run:** anything in AWS. No IAM user, group, role, bucket, SCP or policy was created; no policy simulator
was called; no credential report was downloaded; there are no console screenshots. The deck's lab assumes a
Learner Lab account, and none exists.

`24/24` means the engine agrees with the expectations written from AWS's documented behaviour. It is **not** a
conformance test against the service — no request left this machine. Where a real account could differ, that is
where verification would be needed.

---

## Honest limits

- **The evaluator is deliberately incomplete.** It does not implement `ForAllValues`/`ForAnyValue` set
  operators, session policies, the Organizations OU hierarchy, or wildcards inside `Principal` beyond ARN
  matching. Each is listed on the page with what it would change.
- **The account model is a teaching model.** Six users, two groups, one role — enough to exercise every rule,
  not a real inventory.
- **The remediation is applied to the model, not to AWS.** “14 → 0” shows the rules account for every finding;
  it is not a claim that an account was cleaned.
- **One bug found and fixed:** my first remediation deleted the root user, which AWS does not allow. Root is now
  kept, given MFA, and stripped of access keys.
- **A second bug, found by the audit itself:** the escalation scan initially wrapped an admin policy in a second
  `Statement`, so AdministratorAccess matched nothing. That is exactly the failure a test case catches and an
  eye does not.

---

## How the page is built

- **Hand-written HTML and CSS**, one stylesheet and one script for the whole site. No framework, no build step.
- **Code blocks are copied from the captured run**, with output trimmed by omission (marked with `...`) and
  nothing else altered.
- **Light and dark** through `prefers-color-scheme`; print stylesheet included. No tracking, no cookies.

---

## Answer key

<details>
<summary>Five answers, so you can check yourself before clicking</summary>

| Question | Answer |
|---|---|
| 1 | B |
| 2 | D |
| 3 | B |
| 4 | D |
| 5 | A |

</details>

---

## Files

```
module-08/
├── index.html              the page — 3,863 words
└── README.md               this file

labs/week08/
├── iam_eval.py             six-step evaluator, --test and --explain
├── cases.json              24 requests with expected decisions
├── access_review.py        credential report, findings, escalation, remediation
├── tumaini.json            the case-study account as input
├── tumaini-fixed.json      the same account after remediation
├── findings.json           machine-readable findings
└── access_review.log       captured audit
```

---

<div align="center">

**[← Module 07](../module-07/)** &nbsp;·&nbsp; **[Portfolio](../)** &nbsp;·&nbsp; **[Read the page →](https://mmmmohammed.github.io/cloud-computing-security/module-08/)**

</div>
