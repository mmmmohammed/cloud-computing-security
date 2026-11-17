#!/usr/bin/env python3
"""An AWS-style IAM policy evaluator.

Implements the documented evaluation order rather than a shortcut:

  1. authenticate            (the request names a principal)
  2. collect policies        (identity, resource, boundary, SCP)
  3. explicit deny           any matching Deny ends the decision
  4. guardrails              SCP and permissions boundary must allow
  5. explicit allow          identity or resource policy must allow
  6. implicit deny           no allow means deny

Action and resource matching is wildcard-aware, conditions support the common
operators (Bool, StringEquals/Like, IpAddress, ArnLike, NumericLessThanEquals,
Null), and policy variables such as ${aws:username} are substituted.

Run with --explain to see the six steps for one request, or with --test to run
the case file and check every expected decision.
"""

from __future__ import annotations

import ipaddress
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# matching helpers
# ---------------------------------------------------------------------------
def wildcard_match(pattern: str, value: str, ignore_case: bool = False) -> bool:
    """AWS wildcards: * for any run of characters, ? for one character."""
    if ignore_case:
        pattern, value = pattern.lower(), value.lower()
    p = value_i = 0
    star = -1
    mark = 0
    while value_i < len(value):
        if p < len(pattern) and (pattern[p] == "?" or pattern[p] == value[value_i]):
            p += 1
            value_i += 1
        elif p < len(pattern) and pattern[p] == "*":
            star = p
            mark = value_i
            p += 1
        elif star != -1:
            p = star + 1
            mark += 1
            value_i = mark
        else:
            return False
    while p < len(pattern) and pattern[p] == "*":
        p += 1
    return p == len(pattern)


def as_list(value) -> list:
    return value if isinstance(value, list) else [value]


def substitute(value: str, context: dict) -> str:
    """Replace policy variables like ${aws:username} from the request context."""
    out = value
    for key, replacement in context.items():
        out = out.replace("${" + key + "}", str(replacement))
    return out


def action_matches(statement: dict, action: str) -> bool:
    if "Action" in statement:
        return any(wildcard_match(p, action, ignore_case=True) for p in as_list(statement["Action"]))
    if "NotAction" in statement:
        return not any(wildcard_match(p, action, ignore_case=True) for p in as_list(statement["NotAction"]))
    return False


def resource_matches(statement: dict, resource: str, context: dict) -> bool:
    if "Resource" in statement:
        return any(
            wildcard_match(substitute(p, context), resource) for p in as_list(statement["Resource"])
        )
    if "NotResource" in statement:
        return not any(
            wildcard_match(substitute(p, context), resource) for p in as_list(statement["NotResource"])
        )
    return False


def principal_matches(statement: dict, principal: str) -> bool:
    """Resource policies carry a Principal; identity policies do not."""
    if "Principal" not in statement:
        return True
    declared = statement["Principal"]
    if declared == "*":
        return True
    if isinstance(declared, dict):
        aws = declared.get("AWS", [])
        return any(wildcard_match(substitute(p, {}), principal) for p in as_list(aws))
    return any(wildcard_match(p, principal) for p in as_list(declared))


# ---------------------------------------------------------------------------
# conditions
# ---------------------------------------------------------------------------
def _ip_in(cidr: str, value: str) -> bool:
    try:
        return ipaddress.ip_address(value) in ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False


def condition_value_ok(operator: str, key_value, expected) -> bool:
    expected_list = as_list(expected)
    if operator == "Bool":
        return str(key_value).lower() == str(expected_list[0]).lower()
    if operator == "StringEquals":
        return str(key_value) in [str(e) for e in expected_list]
    if operator == "StringNotEquals":
        return str(key_value) not in [str(e) for e in expected_list]
    if operator == "StringLike":
        return any(wildcard_match(str(e), str(key_value)) for e in expected_list)
    if operator == "ArnLike":
        return any(wildcard_match(str(e), str(key_value)) for e in expected_list)
    if operator == "IpAddress":
        return any(_ip_in(str(e), str(key_value)) for e in expected_list)
    if operator == "NotIpAddress":
        return not any(_ip_in(str(e), str(key_value)) for e in expected_list)
    if operator == "NumericLessThanEquals":
        try:
            return float(key_value) <= float(expected_list[0])
        except (TypeError, ValueError):
            return False
    raise ValueError(f"unsupported condition operator: {operator}")


def conditions_ok(condition: dict, context: dict) -> tuple[bool, str]:
    """All condition blocks must pass. Each block: {operator: {key: value}}."""
    if not condition:
        return True, "no conditions"
    for operator, pairs in condition.items():
        for key, expected in pairs.items():
            if operator == "Null":
                # "true" means the key must be absent
                wants_absent = str(as_list(expected)[0]).lower() == "true"
                present = key in context
                if wants_absent == present:
                    return False, f"{key} {'present' if present else 'absent'} but Null:{expected}"
                continue
            if key not in context:
                # a missing key fails the condition unless the operator is *Not*
                if operator.startswith("StringNot") or operator.startswith("Not"):
                    continue
                return False, f"{key} missing from the request"
            # policy variables are allowed on the expectation side too, which is
            # how ABAC compares a principal tag against a resource tag
            expected_resolved = [substitute(str(e), context) for e in as_list(expected)]
            if not condition_value_ok(operator, context[key], expected_resolved):
                return False, f"{operator} on {key} (had {context[key]!r}, wanted {expected_resolved!r})"
    return True, "conditions met"


# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------
def statement_matches(statement: dict, request: dict) -> tuple[bool, str]:
    action = request["action"]
    resource = request["resource"]
    context = request.get("context", {})

    if not action_matches(statement, action):
        return False, "action"
    if not resource_matches(statement, resource, context):
        return False, "resource"
    if not principal_matches(statement, request["principal"]):
        return False, "principal"
    ok, reason = conditions_ok(statement.get("Condition"), context)
    if not ok:
        return False, reason
    return True, "match"


def evaluate(request: dict, policies: dict) -> dict:
    """Return the decision and the six-step trace that produced it."""
    trace = []
    identity = policies.get("identity", [])
    resource = policies.get("resource", [])
    boundary = policies.get("boundary", [])
    scp = policies.get("scp", [])

    trace.append(("authenticate", f"principal {request['principal']}"))
    trace.append(
        (
            "collect policies",
            f"{len(identity)} identity · {len(resource)} resource · "
            f"{len(boundary)} boundary · {len(scp)} SCP",
        )
    )

    def first_match(statements, effect):
        for idx, stmt in enumerate(statements):
            if stmt.get("Effect") != effect:
                continue
            matched, why = statement_matches(stmt, request)
            if matched:
                return stmt.get("Sid") or f"statement {idx + 1}", stmt
        return None, None

    # 3. explicit deny wins, wherever it appears
    for label, group in (("identity", identity), ("resource", resource), ("boundary", boundary), ("scp", scp)):
        sid, _ = first_match(group, "Deny")
        if sid:
            trace.append(("explicit deny", f"{label} policy {sid}"))
            return {"decision": "DENY", "reason": f"explicit deny in {label} policy {sid}", "trace": trace}
    trace.append(("explicit deny", "none"))

    # 4. guardrails: an SCP or boundary must allow, if either is present
    for label, group in (("SCP", scp), ("permissions boundary", boundary)):
        if not group:
            continue
        sid, _ = first_match(group, "Allow")
        if not sid:
            trace.append(("guardrails", f"{label} allows nothing matching"))
            return {"decision": "DENY", "reason": f"{label} does not allow the action", "trace": trace}
        trace.append(("guardrails", f"{label} allows it ({sid})"))
    if not scp and not boundary:
        trace.append(("guardrails", "no SCP or boundary attached"))

    # 5. an allow from identity or resource policy
    for label, group in (("identity", identity), ("resource", resource)):
        sid, _ = first_match(group, "Allow")
        if sid:
            trace.append(("explicit allow", f"{label} policy {sid}"))
            return {"decision": "ALLOW", "reason": f"allowed by {label} policy {sid}", "trace": trace}
    trace.append(("explicit allow", "none"))

    # 6. default
    return {"decision": "DENY", "reason": "implicit deny — no policy allows this action", "trace": trace}


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------
def run_tests(path: pathlib.Path) -> int:
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    failures = 0
    print(f"{len(cases)} cases from {path.name}\n")
    for case in cases:
        result = evaluate(case["request"], case["policies"])
        ok = result["decision"] == case["expect"]
        failures += 0 if ok else 1
        mark = "ok  " if ok else "FAIL"
        print(f"  {mark} {case['name']}")
        print(f"       {case['request']['action']} on {case['request']['resource']}")
        print(f"       -> {result['decision']} ({result['reason']})")
        if not ok:
            print(f"       expected {case['expect']}")
            for step, detail in result["trace"]:
                print(f"         {step:<15} {detail}")
    print()
    total = len(cases)
    print(f"{total - failures}/{total} decisions match the expectation")
    return 0 if failures == 0 else 1


def explain(path: pathlib.Path, case_name: str) -> int:
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        if case_name.lower() in case["name"].lower():
            result = evaluate(case["request"], case["policies"])
            print(f"request: {case['request']['principal']}")
            print(f"  action   {case['request']['action']}")
            print(f"  resource {case['request']['resource']}")
            for key, value in case["request"].get("context", {}).items():
                print(f"  context  {key} = {value}")
            print()
            for i, (step, detail) in enumerate(result["trace"], 1):
                print(f"  {i}. {step:<17} {detail}")
            print(f"\n  decision: {result['decision']} — {result['reason']}")
            return 0
    print(f"no case matching {case_name!r}")
    return 2


def main() -> int:
    args = sys.argv[1:]
    case_file = HERE / "cases.json"
    if args and args[0] == "--test":
        return run_tests(case_file)
    if args and args[0] == "--explain":
        return explain(case_file, " ".join(args[1:]))
    print(__doc__.strip().splitlines()[0])
    print("\nusage:")
    print("  python3 iam_eval.py --test                 run every case, check the decision")
    print("  python3 iam_eval.py --explain '<name>'     show the six-step trace for one case")
    print("\ncases live in cases.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
