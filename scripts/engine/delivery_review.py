"""Bind a final improvement review to the current checked implementation."""

import hashlib
import json
from pathlib import Path
import re
import uuid


def required(task):
    return task.get("phase") == "implementation" and task.get("level") in ("L2", "L3")


def report_path(task):
    if not re.fullmatch(r"[0-9a-f]{32}", str(task.get("task_id", ""))):
        raise ValueError("Initialized task identity is required for a final review")
    return "work/frontend-policy/evidence/" + task["task_id"] + "/delivery-review.json"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def binding(api, root, task):
    evidence = {}
    for name in task.get("evidence", {}).values():
        path = api.local(root, name)
        evidence[name] = api.sha(path)
        record = api.load(path)
        for artifact in record.get("artifact_hashes", {}):
            evidence[artifact] = api.sha(api.local(root, artifact))
    if task.get("checklist_plan"):
        name = task.get("implementation_checklist")
        evidence[name] = api.sha(api.local(root, name))
    for key in ("packet", "report"):
        name = task.get("independent_review", {}).get(key)
        if name:
            evidence[name] = api.sha(api.local(root, name))
    if api.critic.required(task):
        evidence.update(api.critic.artifacts(api, root, task))
    return {
        "task_id": task["task_id"],
        "policy_hash": api.policy_hash(),
        "contract_hash": api.contract_hash(task),
        "source_hashes": api.hashes(root, task),
        "evidence_hashes": evidence,
    }


def reflection_findings(api, root, reflection, available, source_names=()):
    failures, blockers = [], []
    if not isinstance(reflection, dict):
        return [], ["Final reflection must be a JSON object"]
    checked_results = set(available) - set(source_names)
    rounds = reflection.get("rounds", [])
    if reflection.get("schema") != 1 or not isinstance(rounds, list) or not rounds:
        return [], ["Delivery review needs at least one actual review round"]
    latest = {}
    for number, review in enumerate(rounds, 1):
        observations = review.get("observations", [])
        areas = {item.get("area") for item in observations}
        if not {"rules", "quality", "scope"}.issubset(areas):
            blockers.append(
                "Review round "
                + str(number)
                + " needs rules, quality and scope observations"
            )
        for item in observations:
            if not api.checklist.meaningful(item.get("observed")) or not item.get(
                "evidence"
            ):
                blockers.append(
                    "Review observations need concrete results and actual evidence"
                )
            for name in item.get("evidence", []):
                if name not in available:
                    blockers.append(
                        "Review evidence is outside the current checked artifacts: "
                        + str(name)
                    )
            if not any(name in checked_results for name in item.get("evidence", [])):
                blockers.append(
                    "Review observation needs a current check result, screenshot or execution log"
                )
        seen = set()
        for item in review.get("improvements", []):
            identifier = item.get("id")
            if (
                not identifier
                or identifier in seen
                or not api.checklist.meaningful(item.get("issue"))
            ):
                blockers.append("Improvements need distinct IDs and a concrete issue")
            seen.add(identifier)
            latest[identifier] = item
    for identifier, item in latest.items():
        state = item.get("status")
        if state == "open":
            failures.append(
                "Unresolved improvement "
                + str(identifier)
                + ": "
                + str(item.get("issue"))
            )
        elif state == "blocked":
            blockers.append(
                "Blocked improvement " + str(identifier) + ": " + str(item.get("issue"))
            )
        elif state == "resolved":
            if (
                not api.checklist.meaningful(item.get("action"))
                or not item.get("implementation")
                or not item.get("evidence")
            ):
                blockers.append(
                    "Resolved improvement needs implementation, actual action and recheck evidence: "
                    + str(identifier)
                )
            for name in item.get("implementation", []):
                api.local(root, name)
            for name in item.get("evidence", []):
                if name not in available:
                    blockers.append(
                        "Improvement lacks current recheck evidence: " + str(identifier)
                    )
            if not any(name in checked_results for name in item.get("evidence", [])):
                blockers.append(
                    "Resolved improvement needs an actual recheck result: "
                    + str(identifier)
                )
        else:
            blockers.append("Improvement status missing: " + str(identifier))
    if not isinstance(reflection.get("remaining_improvements"), list):
        blockers.append("Explicitly record the remaining in-scope improvements")
    elif reflection["remaining_improvements"]:
        failures.append("Known in-scope improvements remain before delivery")
    if not api.checklist.meaningful(reflection.get("completion_reason")):
        blockers.append(
            "Explain the current scope and actual basis for ending refinement"
        )
    return failures, blockers


def record(api, root, task, reflection=None, *, reflection_path=None, validator=None):
    current = binding(api, root, task)
    path = report_path(task)
    destination = api.local(root, path, must_exist=False)
    inputs = [api.local(root, name, must_exist=False) for name in api.input_paths(task)]
    inputs.extend(api.local(root, name) for name in current["evidence_hashes"])
    if destination in inputs:
        raise ValueError(
            "Final review output must be separate from source, planning and evidence inputs"
        )
    input_source = None
    if reflection_path is not None:
        reflection_file = api.local(root, reflection_path, must_exist=False)
        if reflection_file == destination:
            raise ValueError("Final observations need their own input file")
    api.save(
        destination,
        {
            "schema": 1,
            "status": "BLOCKED",
            "task_id": task["task_id"],
            "blockers": [
                "A new final review is awaiting valid current observations and checks"
            ],
        },
    )
    if reflection_path is not None:
        reflection = api.load(api.local(root, reflection_path))
        input_source = {
            "path": reflection_path,
            "sha256": api.sha(api.local(root, reflection_path)),
        }
    failures, blockers = reflection_findings(
        api, root, reflection, current["evidence_hashes"], current["source_hashes"]
    )
    validation = (validator or api.verify)(root, task, include_delivery_review=False)
    failures.extend(validation["failures"])
    blockers.extend(
        item
        for item in validation["blockers"]
        if not item.startswith("Visual approval:")
    )
    if binding(api, root, task) != current:
        blockers.append("Implementation or evidence changed during the final review")
    if (
        input_source
        and api.sha(api.local(root, input_source["path"])) != input_source["sha256"]
    ):
        blockers.append("Final observation input changed during review")
    status = "FAIL" if failures else "BLOCKED" if blockers else "READY"
    body = {
        "schema": 1,
        "status": status,
        "binding": current,
        "reflection": reflection,
        "input_source": input_source,
        "failures": list(dict.fromkeys(failures)),
        "blockers": list(dict.fromkeys(blockers)),
        "qualification": "Current scoped review attestation with checked evidence",
    }
    receipt_id = uuid.uuid4().hex
    api.save(
        api.CENTER / "receipts" / (receipt_id + ".json"),
        {
            "runner": "delivery-review",
            "root": str(Path(root).resolve()),
            "task_id": task["task_id"],
            "record_hash": digest(body),
            "policy_hash": api.policy_hash(),
        },
    )
    api.save(destination, {**body, "receipt": receipt_id})
    return {
        "status": status,
        "stage": "delivery-review",
        "report": path,
        "failures": body["failures"],
        "blockers": body["blockers"],
    }


def check(api, root, task):
    if not required(task):
        return {"failures": [], "blockers": []}
    try:
        report = api.load(api.local(root, report_path(task)))
        receipt_id = report.get("receipt", "")
        if len(receipt_id) != 32 or any(
            char not in "0123456789abcdef" for char in receipt_id
        ):
            raise ValueError("Actual delivery-review execution receipt is missing")
        receipt = api.load(api.CENTER / "receipts" / (receipt_id + ".json"))
        body = {key: value for key, value in report.items() if key != "receipt"}
        if receipt != {
            "runner": "delivery-review",
            "root": str(Path(root).resolve()),
            "task_id": task["task_id"],
            "record_hash": digest(body),
            "policy_hash": api.policy_hash(),
        }:
            raise ValueError("Delivery review receipt differs from this task or record")
        current = binding(api, root, task)
        if report.get("binding") != current:
            raise ValueError(
                "Implementation, evidence or rules changed; repeat the final review"
            )
        input_source = report.get("input_source")
        if (
            input_source
            and api.sha(api.local(root, input_source["path"])) != input_source["sha256"]
        ):
            raise ValueError("Final observation input changed; repeat the final review")
        failures, blockers = reflection_findings(
            api,
            root,
            report.get("reflection", {}),
            current["evidence_hashes"],
            current["source_hashes"],
        )
        failures.extend(report.get("failures", []))
        blockers.extend(report.get("blockers", []))
        if report.get("status") != "READY" and not failures and not blockers:
            blockers.append("The final review has not reached READY")
        return {
            "failures": list(dict.fromkeys(failures)),
            "blockers": list(dict.fromkeys(blockers)),
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return {
            "failures": [],
            "blockers": [
                "Delivery review: "
                + str(error)
                + "; run delivery-review against current checks"
            ],
        }
