"""Week 3: the responsibility stack as a single source of truth.

The module calls this table the most important diagram of the week, and the one
learners should be able to redraw from memory. That makes it exactly the thing
that should not exist in two places, so it lives here and module-03/index.html
is checked against it.

Run it from labs/week03:  python3 stack_model.py
Exit code is 1 if the page and this file disagree.
"""
import html as html_mod
import os
import re
import sys

MODELS = [
    ("onprem", "on-prem"),
    ("iaas", "IaaS"),
    ("paas", "PaaS"),
    ("saas", "SaaS"),
]

# Read off the module's table: who manages each layer, per service model.
LAYERS = [
    ("data", "data & access", {"onprem": "you", "iaas": "you", "paas": "you", "saas": "you"}),
    ("applications", "applications", {"onprem": "you", "iaas": "you", "paas": "you", "saas": "provider"}),
    ("runtime", "runtime & middleware", {"onprem": "you", "iaas": "you", "paas": "provider", "saas": "provider"}),
    ("os", "operating system", {"onprem": "you", "iaas": "you", "paas": "provider", "saas": "provider"}),
    ("virtualisation", "virtualisation", {"onprem": "you", "iaas": "provider", "paas": "provider", "saas": "provider"}),
    ("servers", "servers & storage", {"onprem": "you", "iaas": "provider", "paas": "provider", "saas": "provider"}),
    ("network", "networking & facilities", {"onprem": "you", "iaas": "provider", "paas": "provider", "saas": "provider"}),
]


def provider_counts():
    return [sum(1 for _, _, row in LAYERS if row[key] == "provider") for key, _ in MODELS]


def print_table():
    head = f"{'layer':25s}" + "".join(f"{label:>10s}" for _, label in MODELS)
    print(head)
    print("-" * len(head))
    for _, label, row in LAYERS:
        print(f"{label:25s}" + "".join(f"{row[key]:>10s}" for key, _ in MODELS))
    counts = provider_counts()
    summary = " · ".join(f"{label} {n}/7" for (_, label), n in zip(MODELS, counts))
    print(f"\nprovider-managed layers: {summary}")


def check_page(path):
    page = open(path, encoding="utf-8").read()
    problems = []

    rows = re.findall(r'<tr data-layer="([^"]+)">(.*?)</tr>', page, re.S)
    if not rows:
        problems.append("no rows carrying data-layer found")
    seen = {}
    for key, row_html in rows:
        cells = dict(re.findall(r'data-col="([a-z]+)" data-owner="([a-z]+)"', row_html))
        seen[key] = cells
        label = re.search(r'<th scope="row">(.*?)</th>', row_html, re.S)
        label_text = " ".join(html_mod.unescape(re.sub(r"<[^>]+>", "", label.group(1))).split()) if label else ""
        model_label = next((lab for k, lab, _ in LAYERS if k == key), None)
        expected = next((lab for k, lab, _ in LAYERS if k == key), None)
        if model_label is None:
            problems.append(f"page has a layer this file does not know: {key}")
        elif label_text.lower() != expected:
            problems.append(f"label mismatch for {key}: page says '{label_text}', model says '{expected}'")

    for key, label, row in LAYERS:
        if key not in seen:
            problems.append(f"page is missing layer '{key}'")
            continue
        for model, _ in MODELS:
            if model not in seen[key]:
                problems.append(f"page is missing cell {key}/{model}")
            elif seen[key][model] != row[model]:
                problems.append(
                    f"{key}/{model}: page says '{seen[key][model]}', model says '{row[model]}'"
                )

    total_cells = sum(len(c) for c in seen.values())
    label_note = "match" if not any("label" in p for p in problems) else "look at the mismatches above"
    cell_note = "matches the model" if not any("/" in p and ":" in p for p in problems) else "differs — see above"
    print(f"\nchecking {os.path.relpath(path)} ...")
    print(f"  matrix {total_cells} cells: {cell_note}")
    print(f"  layer names: {label_note}")

    # masthead figure: one bar per model, filled segments = provider-managed layers
    stacks = re.findall(r'<div class="ownbar__stack"[^>]*>(.*?)</div>', page, re.S)
    bars = [block.count("seg--provider") for block in stacks]
    expected_bars = provider_counts()
    if bars != expected_bars:
        problems.append(f"bar figure counts {bars} do not match provider layers {expected_bars}")
        print(f"  bar figure counts: {bars} != {expected_bars}")
    else:
        print(f"  bar figure counts: match ({', '.join(map(str, bars))})")

    return problems


if __name__ == "__main__":
    print_table()
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "module-03", "index.html")
    problems = check_page(target)
    if problems:
        print("\nFAIL")
        for problem in problems:
            print("  -", problem)
        sys.exit(1)
    print("OK — page agrees with the source of truth")
