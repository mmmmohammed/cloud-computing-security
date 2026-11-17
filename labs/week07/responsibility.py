#!/usr/bin/env python3
"""Map a sample architecture onto the shared responsibility model, enumerate
STRIDE threats on every data flow, match each threat to the CSA Top Threats
report (2022), assign a control and a named owner, and score provider lock-in
with a concrete exit step per dimension.

No cloud account is used. Inputs are an architecture JSON file; outputs are a
JSON report, a readable text report and an SVG diagram.
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# 1. The shared responsibility model, exactly as taught in the deck.
#    Columns: IaaS, PaaS, SaaS. Values: customer | shared | provider.
# ---------------------------------------------------------------------------
RESPONSIBILITY = [
    ("Data classification & accountability", "customer", "customer", "customer"),
    ("Identity & access management", "customer", "customer", "shared"),
    ("Application security", "customer", "customer", "provider"),
    ("Network controls (firewall rules)", "customer", "shared", "provider"),
    ("Operating system patching", "customer", "provider", "provider"),
    ("Hypervisor & host infrastructure", "provider", "provider", "provider"),
    ("Physical data centre security", "provider", "provider", "provider"),
]

MODEL_COLUMN = {"iaas": 1, "paas": 2, "saas": 3}

# ---------------------------------------------------------------------------
# 2. CSA Top Threats to Cloud Computing, "Pandemic Eleven" (2022).
# ---------------------------------------------------------------------------
CSA_THREATS = {
    1: "Insufficient identity, credential, access and key management",
    2: "Insecure interfaces and APIs",
    3: "Misconfiguration and inadequate change control",
    4: "Lack of cloud security architecture and strategy",
    5: "Insecure software development",
    6: "Unsecure third-party resources",
    7: "System vulnerabilities",
    8: "Accidental cloud data disclosure",
    9: "Misconfiguration and exploitation of serverless and container workloads",
    10: "Organised crime, hackers and APTs",
    11: "Cloud storage data exfiltration",
}

# ---------------------------------------------------------------------------
# 3. STRIDE rules. Each rule fires on a measurable property of a data flow,
#    so the threat list is derived from the architecture, not typed by hand.
# ---------------------------------------------------------------------------
RULES = [
    dict(
        key="no-auth",
        stride="Spoofing",
        when=lambda f, c: not f.get("authenticated", False),
        title="A caller can act on {flow} without proving who it is",
        csa=1,
        row="Identity & access management",
        control="Authenticate every caller (OIDC or STS tokens); no anonymous route to data",
    ),
    dict(
        key="no-mfa",
        stride="Spoofing",
        when=lambda f, c: f.get("authenticated") and not f.get("mfa") and f.get("actor") == "human",
        title="A human session on {flow} needs only a password",
        csa=1,
        row="Identity & access management",
        control="Enforce MFA for every human identity, phishing-resistant where possible",
    ),
    dict(
        key="no-tls",
        stride="Tampering",
        when=lambda f, c: not f.get("encrypted", False),
        title="Traffic on {flow} can be altered in transit",
        csa=2,
        row="Network controls (firewall rules)",
        control="TLS everywhere, including service to service; reject plaintext at the listener",
    ),
    dict(
        key="no-audit",
        stride="Repudiation",
        when=lambda f, c: not f.get("logged", False),
        title="Actions on {flow} leave no attributable record",
        csa=3,
        row="Application security",
        control="Structured audit logs with actor, action, object and time, to a write-once store",
    ),
    dict(
        key="no-throttle",
        stride="Denial of service",
        when=lambda f, c: not f.get("rate_limited", False),
        title="Nothing limits how hard {flow} can be called",
        csa=2,
        row="Network controls (firewall rules)",
        control="Rate limits, quotas and WAF rules at the edge; alert on volume anomalies",
        note="No DoS entry exists in the 2022 list; the closest match is insecure interfaces and APIs.",
    ),
    dict(
        key="no-authz",
        stride="Elevation of privilege",
        when=lambda f, c: not f.get("authorised_per_request", False),
        title="Whatever {flow} carries can be reached by changing an identifier",
        csa=1,
        row="Identity & access management",
        control="Authorise each request against the object, not just the route (block IDOR)",
    ),
    dict(
        key="no-validation",
        stride="Tampering",
        when=lambda f, c: not f.get("validated_input", False),
        title="Input into {flow} reaches the next system unvalidated",
        csa=5,
        row="Application security",
        control="Validate and encode at the boundary; parameterise every query",
    ),
    dict(
        key="public-storage",
        stride="Information disclosure",
        when=lambda f, c: c.get("public_access", False),
        title="{component} is readable without an authenticated identity",
        csa=11,
        row="Data classification & accountability",
        control="Block public access at the account level; serve files through signed URLs",
    ),
    dict(
        key="pii-exposure",
        stride="Information disclosure",
        when=lambda f, c: "pii" in c.get("data_classes", []) and not c.get("field_level_controls", False),
        title="{component} holds personal data with no field-level protection",
        csa=8,
        row="Data classification & accountability",
        control="Classify the data, encrypt it, and mask it outside the paths that need it",
    ),
    dict(
        key="no-sender-auth",
        stride="Spoofing",
        when=lambda f, c: not f.get("sender_authenticated", True),
        title="Mail from {flow} can claim any sender domain",
        csa=6,
        row="Application security",
        owner_hint="customer",
        control="Publish SPF, DKIM and DMARC, and monitor the reports",
        note="SPF, DKIM and DMARC are DNS records, so this stays the customer's even in SaaS — an edge the three-column model does not draw.",
    ),
    dict(
        key="stale-image",
        stride="Elevation of privilege",
        when=lambda f, c: c.get("patch_days", 0) > 30,
        title="{component} has not been patched for {patch_days} days",
        csa=7,
        row="Operating system patching",
        control="Patch on a schedule and rebuild from a current image instead of patching in place",
    ),
]

OWNER_OF = {
    "customer": "customer (the bank's team)",
    "provider": "provider",
    "shared": "shared — provider supplies it, customer must configure it",
}

LOCKIN_EXITS = {
    "data": "export to an open format (CSV, JSON, SQLite) and prove a restore",
    "api": "keep the call graph in Terraform and put a container or adapter in front",
    "contract": "exit clause naming data-return format, timeline, assistance and a price cap",
    "skills": "cross-train on a second provider; keep runbooks vendor-neutral",
}


def responsibility_for(row: str, model: str) -> str:
    """Who owns one row of the model for a given service model.

    A component with model "external" is not a cloud service at all (the
    customer's own handset, say), so the seven rows do not describe it and the
    customer keeps the work.
    """
    if model == "external":
        return "customer"
    for name, *cols in RESPONSIBILITY:
        if name == row:
            return cols[MODEL_COLUMN[model] - 1]
    raise KeyError(f"unknown responsibility row: {row}")


def component_profile(component: dict) -> dict:
    """Count the seven rows for a component's service model."""
    model = component["model"]
    counts = {"customer": 0, "shared": 0, "provider": 0}
    if model == "external":
        return {"counts": counts, "dominant": "external actor", "split": False, "external": True}
    for _name, *cols in RESPONSIBILITY:
        counts[cols[MODEL_COLUMN[model] - 1]] += 1
    top = max(counts.values())
    leaders = [k for k, v in counts.items() if v == top]
    return {
        "counts": counts,
        "dominant": leaders[0] if len(leaders) == 1 else " + ".join(leaders),
        "split": len(leaders) > 1,
    }


def threats_for(flow: dict, components: dict) -> list[dict]:
    """Apply every STRIDE rule to one flow.

    Both ends are considered, but the receiving end is examined first: a flow's
    control usually lives where the request lands, and the first match wins the
    deduplication below.
    """
    found = []
    for end in ("to", "from"):
        ref = flow[end]
        if "component" not in ref:
            continue
        comp = components[ref["component"]]
        for rule in RULES:
            if not rule["when"](flow, comp):
                continue
            model = comp["model"]
            row = rule["row"]
            verdict = rule.get("owner_hint") or responsibility_for(row, model)
            owner = OWNER_OF[verdict]
            title = rule["title"].format(
                flow=flow["id"],
                component=comp["name"],
                patch_days=comp.get("patch_days", "?"),
            )
            found.append(
                {
                    "flow": flow["id"],
                    "stride": rule["stride"],
                    "threat": title,
                    "csa_id": rule["csa"],
                    "csa": CSA_THREATS[rule["csa"]],
                    "responsibility_row": row,
                    "owner": owner,
                    "control": rule["control"],
                    "note": rule.get("note"),
                }
            )
    # One representative per (stride, csa) pair per flow keeps the table readable.
    seen, unique = set(), []
    for t in found:
        key = (t["flow"], t["stride"], t["csa_id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(t)
    return unique


def lockin_score(component: dict) -> dict:
    """Score four dimensions 0 (portable) to 3 (entrenched)."""
    li = component.get("lockin", {})
    if component.get("model") == "external":
        return {"scores": {"data": 0, "api": 0, "contract": 0, "skills": 0}, "total": 0, "max": 12,
                "verdict": "n/a", "exit_steps": {}}
    scores = {
        "data": 0 if li.get("data_format") == "open" else 3,
        "api": 0 if li.get("api") == "open" else 3,
        "contract": 3 if li.get("contract_months", 0) >= 36 else (1 if li.get("contract_months", 0) > 12 else 0),
        "skills": 3 if li.get("skills") == "vendor-only" else 0,
    }
    total = sum(scores.values())
    verdict = "low" if total <= 3 else "moderate" if total <= 6 else "high"
    return {
        "scores": scores,
        "total": total,
        "max": 12,
        "verdict": verdict,
        "exit_steps": {k: LOCKIN_EXITS[k] for k, v in scores.items() if v},
    }


def build_svg(arch: dict, components: dict, threats: list[dict]) -> str:
    """A small, deterministic diagram: one box per component with a stacked bar
    showing how its seven responsibility rows split, plus the flows."""
    colours = {"customer": "#1f6f4a", "shared": "#b45309", "provider": "#334e7d"}
    order = list(arch["components"])
    positions = {}
    for i, key in enumerate(order):
        col, row = i % 3, i // 3
        positions[key] = (40 + col * 300, 150 + row * 185)

    rows = (len(order) + 2) // 3
    w, h = 960, 150 + (rows - 1) * 185 + 140 + 50
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
        'aria-label="Sample architecture with shared-responsibility split per component">',
        '<rect width="100%" height="100%" fill="#fbfaf7"/>',
        '<text x="40" y="52" font-family="Archivo, Helvetica, Arial, sans-serif" font-size="21" font-weight="600" fill="#15171b">'
        "Who secures what — Biashara Bank mobile banking API</text>",
        '<text x="40" y="76" font-family="Archivo, Helvetica, Arial, sans-serif" font-size="12.5" fill="#6b6f76">'
        "Seven responsibility rows per component, split by service model · generated by responsibility.py</text>",
        '<text x="40" y="112" font-family="JetBrains Mono, monospace" font-size="11" fill="#6b6f76">'
        f'{len(components)} components · {len(arch["flows"])} flows · {len(threats)} threats mapped</text>',
    ]

    # legend
    lx = 560
    for label, verdict in (("customer", "customer"), ("shared", "shared"), ("provider", "provider")):
        out.append(f'<rect x="{lx}" y="98" width="11" height="11" fill="{colours[verdict]}"/>')
        out.append(
            f'<text x="{lx + 17}" y="107" font-family="Archivo, Helvetica, Arial, sans-serif" font-size="11" fill="#3a3d42">{label}</text>'
        )
        lx += 100

    # flows first, so boxes sit on top. Several flows can share one pair of
    # components, so their labels are staggered instead of overprinted.
    pairs: dict[tuple, int] = {}
    for flow in arch["flows"]:
        key = (flow["from"].get("component"), flow["to"].get("component"))
        pairs[key] = pairs.get(key, 0) + 1
    placed: dict[tuple, int] = {}

    for flow in arch["flows"]:
        key = (flow["from"].get("component"), flow["to"].get("component"))
        a, b = positions.get(key[0]), positions.get(key[1])
        if a is None or b is None:
            continue
        idx = placed.get(key, 0)
        placed[key] = idx + 1
        stagger = (idx - (pairs[key] - 1) / 2) * 14

        if key[0] == key[1]:
            # a flow that leaves and returns: mark it inside the box instead of
            # drawing a line of zero length
            out.append(
                f'<text x="{a[0] + 206}" y="{a[1] + 20}" text-anchor="end" '
                f'font-family="JetBrains Mono, monospace" font-size="9" fill="#8a8578">\u21ba {flow["id"]}</text>'
            )
            continue

        ax, ay = a[0] + 110, a[1] + 70
        bx, by = b[0] + 110, b[1] + 70
        out.append(
            f'<line x1="{ax}" y1="{ay + stagger}" x2="{bx}" y2="{by + stagger}" stroke="#b9b4a9" stroke-width="1.4" '
            f'stroke-dasharray="{"4 3" if not flow.get("encrypted") else "none"}"/>'
        )
        out.append(
            f'<text x="{(ax + bx) / 2}" y="{(ay + by) / 2 + stagger - 5}" text-anchor="middle" '
            f'font-family="JetBrains Mono, monospace" font-size="9.5" fill="#8a8578">{flow["id"]}</text>'
        )

    for key, comp in components.items():
        x, y = positions[key]
        profile = component_profile(comp)
        out.append(f'<rect x="{x}" y="{y}" width="220" height="140" fill="#ffffff" stroke="#c9c4b8"/>')
        out.append(
            f'<text x="{x + 14}" y="{y + 26}" font-family="Archivo, Helvetica, Arial, sans-serif" font-size="13.5" '
            f'font-weight="600" fill="#15171b">{comp["name"]}</text>'
        )
        model_label = "EXTERNAL" if comp["model"] == "external" else comp["model"].upper()
        out.append(
            f'<text x="{x + 14}" y="{y + 44}" font-family="JetBrains Mono, monospace" font-size="10" fill="#6b6f76">'
            f'{model_label} · {comp.get("provider", "")}</text>'
        )
        # stacked bar: 7 rows
        bx, by, total = x + 14, y + 58, 7
        cursor = bx
        for verdict in ("customer", "shared", "provider"):
            count = profile["counts"][verdict]
            if not count:
                continue
            bw = 190 * count / total
            out.append(f'<rect x="{cursor:.1f}" y="{by}" width="{bw:.1f}" height="9" fill="{colours[verdict]}"/>')
            cursor += bw
        out.append(f'<rect x="{bx}" y="{by}" width="190" height="9" fill="none" stroke="#e2ded4"/>')
        if profile.get("external"):
            counts_text = "not a cloud service"
            verdict_text = "external actor · customer's own"
        else:
            counts_text = (
                f'{profile["counts"]["customer"]} customer · {profile["counts"]["shared"]} shared · '
                f'{profile["counts"]["provider"]} provider'
            )
            verdict_text = "split" if profile["split"] else f'{profile["dominant"]}-owned'
        out.append(
            f'<text x="{x + 14}" y="{y + 84}" font-family="Archivo, Helvetica, Arial, sans-serif" font-size="10.5" fill="#3a3d42">'
            f'{counts_text}</text>'
        )
        out.append(
            f'<text x="{x + 14}" y="{y + 100}" font-family="Archivo, Helvetica, Arial, sans-serif" font-size="10.5" fill="#6b6f76">'
            f'{verdict_text}</text>'
        )
        li = lockin_score(comp)
        lockin_text = "no provider contract" if li["verdict"] == "n/a" else f'lock-in {li["total"]}/12 · {li["verdict"]}'
        out.append(
            f'<text x="{x + 14}" y="{y + 120}" font-family="JetBrains Mono, monospace" font-size="10" fill="#8a8578">'
            f'{lockin_text}</text>'
        )

    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    spec = sys.argv[1] if len(sys.argv) > 1 else "architecture.json"
    arch = json.loads((HERE / spec).read_text(encoding="utf-8"))
    components = arch["components"]

    print(f"architecture: {arch['name']}")
    print(f"  {len(components)} components, {len(arch['flows'])} data flows\n")

    print("shared responsibility model")
    for name, *cols in RESPONSIBILITY:
        print(f"  {name:<38} {' · '.join(f'{c:<8}' for c in cols)}")
    print()

    print("component split")
    for key, comp in components.items():
        profile = component_profile(comp)
        counts = profile["counts"]
        print(
            f"  {comp['name']:<26} {comp['model']:<5} "
            f"customer {counts['customer']} · shared {counts['shared']} · provider {counts['provider']}"
            f"  -> {profile['dominant']}"
        )
    print()

    threats = []
    for flow in arch["flows"]:
        found = threats_for(flow, components)
        threats.extend(found)
        print(f"flow {flow['id']}: {len(found)} threats")
        for t in found:
            print(f"  {t['stride']:<24} CSA #{t['csa_id']}  owner: {t['owner']}")
    print()

    by_owner: dict[str, int] = {}
    for t in threats:
        by_owner[t["owner"]] = by_owner.get(t["owner"], 0) + 1
    print("who owns the work")
    for owner, n in sorted(by_owner.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>2} {'threat ' if n == 1 else 'threats'}  {owner}")
    print()

    print("lock-in")
    for key, comp in components.items():
        li = lockin_score(comp)
        print(f"  {comp['name']:<26} {li['total']}/12 ({li['verdict']})")
        for dim, step in li["exit_steps"].items():
            print(f"      {dim:<9} {step}")
    print()

    report = {
        "architecture": arch["name"],
        "responsibility": [
            {"row": name, "iaas": cols[0], "paas": cols[1], "saas": cols[2]}
            for name, *cols in RESPONSIBILITY
        ],
        "components": {
            k: {"name": c["name"], "model": c["model"], **component_profile(c), "lockin": lockin_score(c)}
            for k, c in components.items()
        },
        "threats": threats,
        "owner_counts": by_owner,
        "csa_coverage": sorted({t["csa_id"] for t in threats}),
    }
    (HERE / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (HERE / "diagram.svg").write_text(build_svg(arch, components, threats), encoding="utf-8")

    print(f"{len(threats)} threats mapped across {len({t['csa_id'] for t in threats})} CSA categories")
    print("wrote report.json and diagram.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
