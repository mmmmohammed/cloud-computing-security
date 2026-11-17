#!/usr/bin/env python3
"""An IAM access review, in the shape of the tools AWS provides.

Stands in for three things that need an AWS account:

  * the credential report   — users, MFA status, key age, key last-used
  * last-accessed analysis  — permissions nothing has used
  * Access Analyzer-ish review — overly broad policies and privilege escalation

Input is a small model of an account (tumaini.json, the case study from the
deck). Output is a findings list with severities, a least-privilege rewrite for
each over-broad role, and — with --fix — a remediated model that is audited
again, so the improvement is measured rather than claimed.
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Pairs of permissions that together allow privilege escalation. Each is a
# documented path: the first permission grants the second's effect.
ESCALATION_PAIRS = [
    ("iam:PassRole", "lambda:CreateFunction", "create a function that runs as a more privileged role"),
    ("iam:PassRole", "ec2:RunInstances", "launch an instance with a more privileged role attached"),
    ("iam:CreatePolicyVersion", "*", "publish a new default version of a policy you are attached to"),
    ("iam:AttachUserPolicy", "*", "attach AdministratorAccess to yourself"),
    ("iam:AttachGroupPolicy", "*", "attach AdministratorAccess to your own group"),
    ("iam:PutUserPolicy", "*", "write an inline policy granting yourself anything"),
    ("iam:UpdateAssumeRolePolicy", "*", "make a trusted role trust you"),
    ("iam:CreateAccessKey", "*", "mint a key for a more privileged user"),
    ("sts:AssumeRole", "*", "assume any role in the account that trusts the account"),
]


def statements_of(policy) -> list[dict]:
    """Accept either a policy document or a single statement — role policies in
    this model are written as bare statements, which is also how people paste
    them into inline policies."""
    if isinstance(policy, dict):
        if "Statement" in policy:
            return policy["Statement"]
        if "Effect" in policy:
            return [policy]
    return []


def grants(policy, action: str) -> bool:
    """Does this policy allow the action? Wildcards and '*' both count."""
    for stmt in statements_of(policy):
        if stmt.get("Effect") != "Allow":
            continue
        if "Action" in stmt:
            actions = stmt["Action"] if isinstance(stmt["Action"], list) else [stmt["Action"]]
            for a in actions:
                a = a.lower()
                if a == "*" or a == action.lower() or a.endswith(":*") and action.lower().startswith(a[:-1]):
                    return True
        if "NotAction" in stmt:
            excluded = stmt["NotAction"] if isinstance(stmt["NotAction"], list) else [stmt["NotAction"]]
            if action not in excluded:
                return True
    return False


def is_wildcard(policy) -> bool:
    """A service wildcard on every resource is as broad as '*' in practice."""
    for stmt in statements_of(policy):
        if stmt.get("Effect") != "Allow":
            continue
        actions = stmt.get("Action")
        actions = actions if isinstance(actions, list) else [actions]
        resources = stmt.get("Resource")
        resources = resources if isinstance(resources, list) else [resources]
        if "*" not in resources:
            continue
        if any(a == "*" or a.endswith(":*") for a in actions):
            return True
    return False


def find(account: dict) -> list[dict]:
    findings: list[dict] = []

    def add(sev, area, title, evidence, fix):
        findings.append({"severity": sev, "area": area, "title": title, "evidence": evidence, "fix": fix})

    for user in account["users"]:
        name = user["name"]
        if user.get("root"):
            if not user.get("mfa"):
                add("critical", "root", "Root user has no MFA",
                    "root account can sign in with a password alone",
                    "Enable MFA on root, then store the credentials offline")
            for key in user.get("keys", []):
                add("critical", "root", "Root user has an active access key",
                    f"key {key['id']} created {key['age_days']} days ago, last used {key['last_used_days']} days ago",
                    "Delete the root access key; nothing should call AWS as root")
            continue

        if user.get("employment", "current") == "left":
            add("critical", "identity", f"Departed employee {name} still has an active key",
                "the account remains usable by whoever holds the key",
                "Disable the user and its keys now, then review CloudTrail for its use")
            continue  # hygiene findings are noise next to "delete this account"

        if not user.get("mfa"):
            add("high", "identity", f"{name} has no MFA",
                "console or API access without a second factor",
                "Enforce MFA, then require it in policy with aws:MultiFactorAuthPresent")
        if user.get("shared_by", 1) > 1:
            add("high", "identity", f"{name} is shared by {user['shared_by']} people",
                "CloudTrail records the user, never the human", 
                "Issue one identity per person, or federate to remove IAM users entirely")
        for key in user.get("keys", []):
            if key["age_days"] > 90:
                add("medium", "keys", f"{name}'s key is {key['age_days']} days old",
                    f"key {key['id']} is past a 90-day rotation window",
                    "Rotate the key; better, remove it and use a role")
            if key["last_used_days"] > 90:
                add("medium", "keys", f"{name}'s key has not been used in {key['last_used_days']} days",
                    "an unused credential is attack surface with no owner",
                    "Deactivate the key, then delete it after a grace period")

    for group in account.get("groups", []):
        for policy_name in group.get("policies", []):
            if policy_name in ("AdministratorAccess", "PowerUserAccess"):
                members = [u["name"] for u in account["users"] if group["name"] in u.get("groups", [])]
                add("high", "policy", f"Group {group['name']} carries {policy_name}",
                    f"members: {', '.join(members) or 'none listed'} — full control of the account",
                    "Replace with a scoped policy; keep admin in a break-glass role with MFA and alerting")

    for role in account.get("roles", []):
        for policy in role.get("policies", []):
            if is_wildcard(policy):
                add("high", "policy", f"Role {role['name']} has a wildcard allow",
                    "Action '*' or a service wildcard with Resource '*'",
                    "Scope the action and the resource ARN to what the workload uses")
        needed = role.get("needed")
        if needed:
            broader = [
                p for p in role.get("policies", [])
                if grants(p, needed["action"]) and not any(
                    needed["resource"] in str(s.get("Resource", "")) or str(s.get("Resource", "")) == needed["resource"]
                    for s in statements_of(p)
                    if s.get("Effect") == "Allow"
                )
            ]
            if broader or len(role.get("policies", [])) > 1:
                add("medium", "policy", f"Role {role['name']} exceeds what it uses",
                    f"it needs {needed['action']} on {needed['resource']}",
                    "Replace with the minimal statement below")

    # privilege escalation: two permissions in the same policy set
    policy_sets = []
    for group in account.get("groups", []):
        policy_sets.append((f"group {group['name']}", group.get("policies", [])))
    for role in account.get("roles", []):
        policy_sets.append((f"role {role['name']}", role.get("policies", [])))
    for user in account["users"]:
        if user.get("policies"):
            policy_sets.append((f"user {user['name']}", user["policies"]))

    for label, policies in policy_sets:
        blob = []
        for p in policies:
            if isinstance(p, str):
                if p in ("AdministratorAccess", "PowerUserAccess"):
                    # a managed admin policy, expanded to the statement it grants
                    blob.append({"Effect": "Allow", "Action": "*", "Resource": "*"})
            else:
                blob.extend(statements_of(p))
        # one finding per policy set, however many pairs match — nine copies of
        # the same finding is how a report gets ignored
        paths = [
            (first, second, why)
            for first, second, why in ESCALATION_PAIRS
            if any(grants({"Statement": [s]}, first) for s in blob)
            and any(grants({"Statement": [s]}, second) for s in blob)
        ]
        if paths:
            listed = "; ".join(f"{a} + {b}" for a, b, _ in paths[:3])
            more = f" and {len(paths) - 3} more" if len(paths) > 3 else ""
            add("high", "escalation", f"{label} can escalate its own privileges",
                f"{len(paths)} path(s): {listed}{more}. For example, {paths[0][2]}.",
                "Remove one side of each pair, or add a permissions boundary and an SCP")

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["area"]))
    return findings


def credential_report(account: dict) -> list[dict]:
    rows = []
    for user in account["users"]:
        keys = user.get("keys", [])
        rows.append(
            {
                "user": user["name"],
                "mfa": "yes" if user.get("mfa") else "NO",
                "keys": len(keys),
                "oldest_key_days": max((k["age_days"] for k in keys), default=0),
                "last_used_days": min((k["last_used_days"] for k in keys), default=None),
                "note": "shared by %d" % user["shared_by"] if user.get("shared_by", 1) > 1 else
                        ("departed" if user.get("employment") == "left" else
                         ("ROOT" if user.get("root") else "")),
            }
        )
    rows.sort(key=lambda r: (r["mfa"] != "NO", -(r["oldest_key_days"] or 0)))
    return rows


def least_privilege(account: dict) -> list[dict]:
    """The minimal policy each role's own usage argues for."""
    out = []
    for role in account.get("roles", []):
        needed = role.get("needed")
        if not needed:
            continue
        out.append(
            {
                "role": role["name"],
                "current": role.get("policies", []),
                "proposed": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "OnlyWhatTheFunctionUses",
                            "Effect": "Allow",
                            "Action": [needed["action"]],
                            "Resource": [needed["resource"]],
                        }
                    ],
                },
            }
        )
    return out


def remediate(account: dict) -> dict:
    """Apply the fixes the findings call for, so the audit can be re-run."""
    fixed = json.loads(json.dumps(account))
    fixed["users"] = [u for u in fixed["users"] if u.get("employment") != "left"]
    for user in fixed["users"]:
        user["mfa"] = True
        user["shared_by"] = 1
        if user.get("root"):
            # root cannot be deleted; it can be stripped of keys and given MFA
            user["keys"] = []
            continue
        for key in user.get("keys", []):
            key["age_days"] = 0
            key["last_used_days"] = 0
    for group in fixed.get("groups", []):
        group["policies"] = ["ScopedDeveloperPolicy"] if group.get("policies") else group.get("policies", [])
    for role in fixed.get("roles", []):
        needed = role.get("needed")
        if needed:
            role["policies"] = [
                {
                    "Sid": "OnlyWhatTheFunctionUses",
                    "Effect": "Allow",
                    "Action": [needed["action"]],
                    "Resource": [needed["resource"]],
                }
            ]
    return fixed


def report(account: dict, findings: list[dict], verbose: bool = True) -> None:
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    if verbose:
        print(f"credential report · {account['account']}")
        print(f"  {'user':<18}{'mfa':<5}{'keys':<6}{'oldest key':<12}{'last used':<11}note")
        for r in credential_report(account):
            last = f"{r['last_used_days']}d" if r["last_used_days"] is not None else "—"
            print(f"  {r['user']:<18}{r['mfa']:<5}{r['keys']:<6}{r['oldest_key_days']:<12}{last:<11}{r['note']}")
        print()
        print(f"{len(findings)} findings")
        for f in findings:
            print(f"  [{f['severity'].upper():<8}] {f['title']}")
            print(f"             {f['evidence']}")
            print(f"             fix: {f['fix']}")
        print()
        for proposal in least_privilege(account):
            current = proposal["current"]
            stmt = statements_of(current[0])[0] if current else {}
            action = stmt.get("Action")
            resource = stmt.get("Resource")
            proposed = proposal["proposed"]["Statement"][0]
            print(f"least privilege · {proposal['role']}")
            print(f"  before: {action} on {resource}")
            print(f"  after : {proposed['Action']} on {proposed['Resource']}")
        print()
    summary = " · ".join(f"{counts.get(s, 0)} {s}" for s in ("critical", "high", "medium", "low"))
    print(f"summary: {summary}")


def main() -> int:
    path = HERE / (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "tumaini.json")
    account = json.loads(path.read_text(encoding="utf-8"))
    findings = find(account)
    report(account, findings)

    payload = {
        "account": account["account"],
        "findings": findings,
        "credential_report": credential_report(account),
        "least_privilege": least_privilege(account),
    }
    (HERE / "findings.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if "--fix" in sys.argv:
        print()
        fixed = remediate(account)
        after = find(fixed)
        (HERE / "tumaini-fixed.json").write_text(json.dumps(fixed, indent=2) + "\n", encoding="utf-8")
        print("after remediation")
        for f in after:
            print(f"  [{f['severity'].upper():<8}] {f['title']}")
        print(f"  {len(findings)} findings before, {len(after)} after")

    print("wrote findings.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
