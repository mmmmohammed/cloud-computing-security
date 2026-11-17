<div align="center">

# 03 · Service and deployment models

**Who patches the operating system? That is the whole question.** IaaS, PaaS and SaaS are usually taught
as three lists of examples. This module treats them as one seven-layer stack where the responsibility line
moves down as you climb the models — then measures what that line actually costs, by serving the same page
two ways and checking a machine-readable version of the matrix on every run.

![module](https://img.shields.io/badge/module-03%20of%2015-bc4c00?style=flat-square)
![matrix](https://img.shields.io/badge/matrix-28%20cells%20%C2%B7%20machine%20checked-1f6feb?style=flat-square)
![lab](https://img.shields.io/badge/lab-nginx%20vs%20http.server%2C%20measured-2ea043?style=flat-square)
![deps](https://img.shields.io/badge/dependencies-none-6e7781?style=flat-square)

[**Read the page →**](https://mmmmohammed.github.io/cloud-computing-security/module-03/) &nbsp;·&nbsp;
[← Module 02](../module-02/) &nbsp;·&nbsp;
[Portfolio](../)

</div>

---

## What this module demonstrates

| Skill | Evidence in this folder |
|---|---|
| **Turning a diagram into data** | `stack_model.py` holds the 7 × 4 matrix; the page is checked against it and the script exits non-zero on any disagreement. 28 cells, layer names and the four ownership bars all verified. |
| **Reasoning about shared responsibility** | The same stack read four times: what the provider takes at each model, and what remains yours — including the layer everyone forgets, *data and access*, which never leaves your side. |
| **Judgement about deployment, not ranking** | Public, private, community and hybrid compared as trades, with the community cloud that exists because of regulation (GovCloud, launched 2011) and the Kenya Data Protection Act residency requirement. |
| **Measuring a configuration trade** | One page, two servers: 21 lines of nginx config against a zero-config one-liner. Same speed; different exposure. |

---

## Check it in two minutes

| Look at | What it shows |
|---|---|
| [The page](https://mmmmohammed.github.io/cloud-computing-security/module-03/) | The matrix, filterable one model at a time |
| [`labs/week03/stack_model.py`](../labs/week03/stack_model.py) | The model, the table printer, and the page checker |
| [`labs/week03/serve_compare.py`](../labs/week03/serve_compare.py) | Start-up, TTFB, server header and directory-listing exposure, measured |
| [`labs/week03/serve_compare.json`](../labs/week03/serve_compare.json) | The measurements the page quotes |

---

## The matrix

```
                        on-prem    IaaS    PaaS    SaaS
data & access              you     you     you     you     ← never leaves your side
applications               you     you     you   provider
runtime & middleware       you     you  provider provider
operating system           you     you  provider provider
virtualisation             you  provider provider provider
servers & storage          you  provider provider provider
networking & facilities    you  provider provider provider
                        ─────────────────────────────────
provider-managed             0       3       5       6      of 7
```

Read the column, not the row: at SaaS the provider runs six of seven layers and you still own the one
that carries the personal data — which is precisely why "we moved to SaaS, so security is handled" is the
most expensive sentence in the module.

---

## What the page covers

| # | Section | What it argues |
|---|---|---|
| 01 | [The stack](https://mmmmohammed.github.io/cloud-computing-security/module-03/#stack) | Seven layers, one interactive matrix, four ownership bars. |
| 02 | [The three models](https://mmmmohammed.github.io/cloud-computing-security/module-03/#models) | Each model component by component, with what you are still accountable for. |
| 03 | [Emerging models](https://mmmmohammed.github.io/cloud-computing-security/module-03/#emerging) | FaaS, DBaaS, SECaaS and the rest — all moving the same line, none erasing it. |
| 04 | [Deployment models](https://mmmmohammed.github.io/cloud-computing-security/module-03/#deployment) | Public, private, community, hybrid, and the fifth thing people call a model that is not one. |
| 05 | [Choosing](https://mmmmohammed.github.io/cloud-computing-security/module-03/#compare) | A trade, not a ranking — with the factors that actually decide it. |
| 06 | [Community cloud](https://mmmmohammed.github.io/cloud-computing-security/module-03/#community) | GovCloud and residency: when regulation, not engineering, picks the model. |
| 07 | [A real scenario](https://mmmmohammed.github.io/cloud-computing-security/module-03/#choose) | Mwangaza University, decided in a table. |
| 08 | [Security by model](https://mmmmohammed.github.io/cloud-computing-security/module-03/#security) | What you still have to secure at each model — the split that matters. |
| 09 | [The lab](https://mmmmohammed.github.io/cloud-computing-security/module-03/#lab) | The account half marked not run; the measurable half done properly. |
| 10 | [Quiz](https://mmmmohammed.github.io/cloud-computing-security/module-03/#quiz) | Five questions on the Mwangaza case. |

---

## The lab — one page, two servers

The lab sheet asks for EC2, Elastic Beanstalk and Google Forms. That needs accounts I do not have, so it
is marked **not run** on the page rather than written up as if it happened. What I could do is the
comparison the lab is really after: the same page served by a server I configured and by one that
configures itself.

### Run it

```bash
cd labs/week03
python3 serve_compare.py     # starts both servers, measures, stops them, writes JSON
python3 stack_model.py       # prints the matrix and validates the page against it
```

Requirements: `nginx` on `PATH`, Python 3, ports 8081 and 8082 free. `serve_compare.py` checks the ports
first and refuses to run rather than fighting an existing server.

### What it measured

| Measure | nginx, configured by me | `python3 -m http.server` |
|---|---|---|
| Configuration written | **21 lines** | **0 lines** |
| Launch to first 200 | 0.05 s | 0.06 s |
| Time to first byte | 0.41 ms | 0.78 ms |
| Server header | `nginx` | `SimpleHTTP/0.6 Python/3.14.8` |
| `GET /sub/` | **403 — refused** | **200 — lists every file** |

### What the numbers mean

- **The timings are noise.** Both answer in about a millisecond. Anyone claiming nginx is "faster" at
  serving one static file is not measuring what they think they are.
- **The differences that matter are the other three rows.** The one-liner publishes its exact runtime and
  hands out a directory listing to anyone who guesses a folder name — and there is no configuration file
  to change that, because there is no configuration.
- **The 21 lines buy three decisions:** `server_tokens off`, `autoindex off`, and a document root I chose.
  That is the module in miniature — in IaaS the defaults are yours to get wrong; in PaaS someone else has
  already thought about them, and you inherit their answer.
- **What the harness taught me:** the first run left nginx listening on port 8081 after the script
  finished. nginx daemonises, so the process I launched exited immediately and my cleanup was watching a
  dead parent. The fix was `daemon off;` in the config — a one-line lesson in knowing which process you are
  actually talking to.

### The validator

```bash
$ python3 stack_model.py
layer                       on-prem      IaaS      PaaS      SaaS
-----------------------------------------------------------------
data & access                   you       you       you       you
applications                    you       you       you  provider
runtime & middleware            you       you  provider  provider
operating system                you       you  provider  provider
virtualisation                  you  provider  provider  provider
servers & storage               you  provider  provider  provider
networking & facilities         you  provider  provider  provider

provider-managed layers: on-prem 0/7 · IaaS 3/7 · PaaS 5/7 · SaaS 6/7

checking ../../module-03/index.html ...
  matrix 28 cells: matches the model
  layer names: match
  bar figure counts: match (0, 3, 5, 6)
OK — page agrees with the source of truth
```

The diagram is a claim, and claims should be checked. If someone edits a cell in the page, the script
fails — the same instinct as a test, applied to documentation.

---

## How the page is built

- **Hand-written HTML and CSS**, sharing one stylesheet and one script with modules 01 and 02.
- **The matrix is a real table** with `data-col` and `data-owner` attributes, so it is readable without
  JavaScript, searchable with the browser's find, and parseable by the validator. The filter buttons only
  change emphasis — they never change the data.
- **Accessible interaction:** filter chips are buttons with `aria-pressed`, the summary line is generated
  from the DOM rather than typed by hand, and every cell carries screen-reader text ("provider manages").
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
| 3 | A |
| 4 | B |
| 5 | A |

</details>

---

## Honest limits

- **The account half was not run:** EC2 with nginx, the same page on Elastic Beanstalk, an equivalent
  Google Form. No AWS or Google account, so no console evidence — stated on the page, in the lab section,
  where a reader will see it.
- nginx and `http.server` are **stand-ins for the models, not the models**. A one-line Python server has
  some of PaaS's shape — no configuration, defaults you inherit — but it is not Elastic Beanstalk, and the
  page does not claim otherwise.
- Timings are from a single machine and move by a few tenths of a millisecond between runs; the numbers on
  the page are the ones in `serve_compare.json`.

---

## Files

```
module-03/
├── index.html          the page — 2,739 words, 49 KB, no runtime dependencies
└── README.md           this file

labs/week03/
├── serve_compare.py        starts nginx + http.server, measures, stops both, writes JSON
├── nginx.conf              the 21 lines — document root, server_tokens off, autoindex off
├── serve_compare.json      measured results quoted on the page
├── serve_compare.log       captured console output
├── stack_model.py          the matrix as data + page checker (exits 1 on drift)
├── stack_check.log         captured validator output quoted on the page
├── site/hello.html         the page served by both servers
└── site/sub/notes.txt      the directory that separates "refused" from "listed"
```

---

<div align="center">

**[← Module 02](../module-02/)** &nbsp;·&nbsp; **[Portfolio](../)** &nbsp;·&nbsp; **[Read the page →](https://mmmmohammed.github.io/cloud-computing-security/module-03/)**

</div>
