"""Derive a readable implementation checklist from current scoped evidence."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

GENERIC = {
    "待做",
    "已验证",
    "通过",
    "符合",
    "正常",
    "遵循规则",
    "按要求实现",
    "pending",
    "pass",
    "passed",
    "ok",
    "looks good",
}


def applicable(task):
    return task.get("phase") == "implementation" and (
        task.get("level") == "L3" or bool(task.get("checklist_plan"))
    )


def meaningful(value):
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value.strip().lower() not in GENERIC
    )


def read_plan(api, root, task):
    plan = api.load(api.local(root, task.get("checklist_plan")))
    if plan.get("schema") != 1 or not isinstance(plan.get("entries"), list):
        raise ValueError("Checklist plan needs schema=1 and entries")
    return plan["entries"]


def expected_ids(task):
    return {
        "rule:" + item["id"]
        for item in task.get("rule_application", [])
        if item.get("applicability") == "applicable"
    } | {"project:" + item["id"] for item in task.get("project_requirements", [])}


def planning_gaps(api, root, task):
    if not applicable(task):
        return []
    if not task.get("checklist_plan"):
        return [
            "Checklist: migrate the L3 checklist to a frozen checklist_plan JSON and derived implementation_checklist Markdown"
        ]
    try:
        entries = read_plan(api, root, task)
        seen = set()
        gaps = []
        checks = {item["id"]: item for item in task.get("checks", [])}
        expected = expected_ids(task)
        for entry in entries:
            identifier = entry.get("id")
            if identifier in seen or identifier not in expected:
                gaps.append(
                    "Checklist: duplicate or undeclared requirement " + str(identifier)
                )
            seen.add(identifier)
            if not all(
                meaningful(entry.get(key)) for key in ("decision", "condition")
            ) or not entry.get("implementation"):
                gaps.append(
                    "Checklist: concrete decision, condition and implementation needed for "
                    + str(identifier)
                )
            for name in entry.get("implementation", []):
                api.local(root, name, must_exist=False)
            verification = entry.get("verification", {})
            check = checks.get(verification.get("check_id"), {})
            if not check:
                gaps.append("Checklist: planned check missing for " + str(identifier))
            if (
                verification.get("method")
                in ("real_touch", "focus_audit", "screen_reader")
                and check.get("type") != "review"
            ):
                gaps.append(
                    "Checklist: device and accessibility methods need their specific actual review observation "
                    + str(identifier)
                )
            if (
                check.get("type") == "review"
                and verification.get("criterion") != identifier
            ):
                gaps.append(
                    "Checklist: review criterion must identify its exact rule/project item "
                    + str(identifier)
                )
            if check.get("type") == "browser" and (
                not all(key in verification for key in ("page", "width", "state"))
                or not str(
                    verification.get("assertion", {}).get("action", "")
                ).startswith("expect_")
            ):
                gaps.append(
                    "Checklist: browser item needs its viewport/state and actual assertion "
                    + str(identifier)
                )
        gaps.extend(
            "Checklist: missing planned requirement " + identifier
            for identifier in sorted(expected - seen)
        )
        report = api.local(root, task.get("implementation_checklist"), must_exist=False)
        protected = [
            api.local(root, name, must_exist=False) for name in api.input_paths(task)
        ]
        if report.suffix.lower() not in (".md", ".markdown") or report in protected:
            gaps.append(
                "Checklist: generated Markdown must have its own path outside registered source, planning and evidence inputs"
            )
        return gaps
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return ["Checklist: invalid plan: " + str(exc)]


def evidence_result(api, root, task, entry, routes):
    verification = entry["verification"]
    identifier = entry["id"]
    check = next(
        item for item in task["checks"] if item["id"] == verification["check_id"]
    )
    method = (
        routes.get(identifier.removeprefix("rule:"), {}).get("method")
        if identifier.startswith("rule:")
        else None
    )
    if method in ("workflow", "tool_provenance") and check["type"] != "review":
        return (
            "BLOCKED",
            "This item needs its actual workflow/tool evidence and specific review observation",
            [],
        )
    for name in entry["implementation"]:
        api.local(root, name)
    if check["type"] == "source":
        if method != "automated":
            return "BLOCKED", "Source scan does not establish this requirement", []
        findings = api.source_findings(root, task)
        return (
            ("FAIL", "; ".join(findings), task.get("files", []))
            if findings
            else (
                "VERIFIED",
                "Current source scan completed within declared file scope",
                task.get("files", []),
            )
        )
    record_name = task.get("evidence", {}).get(check["id"])
    record = api.load(api.local(root, record_name))
    current = api.hashes(root, task, include_runtime=check["type"] != "command")
    if (
        record.get("task_id") != task["task_id"]
        or record.get("type") != check["type"]
        or record.get("source_hashes") != current
    ):
        return (
            "BLOCKED",
            "Evidence is stale or belongs to a different task/type",
            [record_name],
        )
    if any(
        api.sha(api.local(root, name)) != digest
        for name, digest in record.get("artifact_hashes", {}).items()
    ):
        return "BLOCKED", "Registered evidence artifact changed", [record_name]
    if check["type"] in ("browser", "command"):
        runner = (
            "fixed-browser-process" if check["type"] == "browser" else "command-process"
        )
        if not api.execution_valid(root, task, record, runner):
            return (
                "BLOCKED",
                "Actual execution receipt is missing or stale",
                [record_name],
            )
        if (
            record.get("status") == "FAIL"
            or record.get("runner_error")
            or (check["type"] == "command" and record.get("exit_code") != 0)
        ):
            return (
                "FAIL",
                record.get("runner_error") or "The bound execution failed",
                [record_name],
            )
    if check["type"] == "command":
        log = api.local(root, record.get("log"))
        if not record.get("command") or api.sha(log) != record.get("log_sha256"):
            return (
                "BLOCKED",
                "Command/log identity is missing or changed",
                [record_name],
            )
        return (
            "VERIFIED",
            "Executed "
            + json.dumps(record["command"], ensure_ascii=False)
            + " with exit code 0",
            [record_name, record["log"]],
        )
    if check["type"] == "browser":
        assertion = verification["assertion"]
        matching = [
            item
            for item in record.get("assertions", [])
            if all(
                item.get(key) == verification[key] for key in ("page", "width", "state")
            )
            and assertion in item.get("checks", [])
        ]
        if not matching:
            return (
                "BLOCKED",
                "No matching executed page/viewport/state assertion",
                [record_name],
            )
        return (
            "VERIFIED",
            "Executed "
            + json.dumps(assertion, ensure_ascii=False)
            + " at "
            + json.dumps(
                {key: verification[key] for key in ("page", "width", "state")},
                ensure_ascii=False,
            ),
            [record_name],
        )
    if check["type"] == "review":
        matches = [
            item
            for item in record.get("observations", [])
            if item.get("criterion") == identifier
        ]
        if len(matches) != 1:
            return (
                "BLOCKED",
                "One specific observation is required for this criterion",
                [record_name],
            )
        observation = matches[0]
        evidence = observation.get("evidence", [])
        if (
            not meaningful(observation.get("observed"))
            or not meaningful(observation.get("location"))
            or not evidence
        ):
            return (
                "BLOCKED",
                "Specific actual observation, location and evidence are required",
                [record_name],
            )
        for name in evidence:
            if record.get("artifact_hashes", {}).get(name) != api.sha(
                api.local(root, name)
            ):
                return (
                    "BLOCKED",
                    "Observation evidence is not bound to the review record",
                    [record_name],
                )
        if observation.get("status") == "FAIL":
            return "FAIL", observation["observed"], [record_name, *evidence]
        required_method = verification.get("method")
        if (
            required_method in ("real_touch", "focus_audit", "screen_reader")
            and observation.get("method") != required_method
        ):
            return (
                "BLOCKED",
                "Required actual verification method remains unverified: "
                + required_method,
                [record_name],
            )
        details = observation.get("verification_details", {})
        if required_method in ("real_touch", "focus_audit", "screen_reader"):
            complete = all(
                meaningful(details.get(key))
                for key in ("environment", "tool", "coverage", "expected", "actual")
            )
            steps = details.get("steps", [])
            if (
                not complete
                or not isinstance(steps, list)
                or not steps
                or not all(meaningful(step) for step in steps)
            ):
                return (
                    "BLOCKED",
                    "Actual environment, tool, complete scoped steps and expected/actual results are missing",
                    [record_name, *evidence],
                )
        if observation.get("status") != "PASS":
            return "BLOCKED", observation["observed"], [record_name, *evidence]
        actual = "Review attestation " + observation["observed"]
        if required_method in ("real_touch", "focus_audit", "screen_reader"):
            actual += "\n\n实测记录 " + json.dumps(details, ensure_ascii=False)
        return "VERIFIED", actual, [record_name, *evidence]
    return "BLOCKED", "This check type has no item-specific result adapter", []


def render(rows):
    lines = [
        "# 逐项落实结果",
        "",
        "结果依据当前执行记录与观察重新计算。VERIFIED 保留对应验证范围。",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                "## " + row["id"],
                "",
                "状态 " + row["status"],
                "",
                "设计决定 " + row["decision"],
                "",
                "通过条件 " + row["condition"],
                "",
                "实际结果 " + row["actual"],
                "",
                "实现位置 " + ", ".join(row["implementation"]),
                "",
                "证据 " + ", ".join(row["evidence"]),
                "",
            ]
        )
    return "\n".join(lines)


class _EvidenceSnapshot:
    """Reuse reads inside one batch, then recheck their actual contents."""

    def __init__(self, api):
        self.original = api
        self.values = {}
        self.digests = {}
        self.paths = {}
        self.inputs = {}
        self.executions = {}
        self.source_result = None
        self.policy = api.policy_hash() if hasattr(api, "policy_hash") else None
        self.api = SimpleNamespace(**vars(api))
        for name in (
            "local",
            "load",
            "sha",
            "hashes",
            "execution_valid",
            "source_findings",
        ):
            setattr(self.api, name, getattr(self, name))

    def local(self, root, value, must_exist=True):
        key = (str(root), value, must_exist)
        if key not in self.paths:
            self.paths[key] = self.original.local(root, value, must_exist=must_exist)
        return self.paths[key]

    def sha(self, path):
        path = Path(path)
        if path not in self.digests:
            self.digests[path] = self.original.sha(path)
        return self.digests[path]

    def load(self, path):
        path = Path(path)
        if path not in self.values:
            before = self.sha(path)
            value = self.original.load(path)
            if self.original.sha(path) != before:
                raise ValueError("Evidence changed while it was being read")
            self.values[path] = value
        return self.values[path]

    def hashes(self, root, task, include_runtime=True):
        if include_runtime not in self.inputs:
            self.inputs[include_runtime] = (
                root,
                task,
                self.original.hashes(root, task, include_runtime=include_runtime),
            )
        return self.inputs[include_runtime][2]

    def execution_valid(self, root, task, record, runner):
        key = (id(record), runner)
        if key not in self.executions:
            valid = self.original.execution_valid(root, task, record, runner)
            self.executions[key] = (root, task, record, runner, valid)
        return self.executions[key][4]

    def source_findings(self, root, task):
        if self.source_result is None:
            self.hashes(root, task)
            self.source_result = self.original.source_findings(root, task)
        return self.source_result

    def stability_gaps(self):
        try:
            if self.policy is not None and self.original.policy_hash() != self.policy:
                return ["Checklist: policy changed during derivation"]
            for (root, value, must_exist), expected in self.paths.items():
                if self.original.local(root, value, must_exist=must_exist) != expected:
                    return ["Checklist: an input path changed during derivation"]
            for path, expected in self.digests.items():
                if self.original.sha(path) != expected:
                    return ["Checklist: input or evidence changed during derivation"]
            for include_runtime, (root, task, expected) in self.inputs.items():
                if (
                    self.original.hashes(root, task, include_runtime=include_runtime)
                    != expected
                ):
                    return ["Checklist: implementation changed during derivation"]
            for root, task, record, runner, expected in self.executions.values():
                if (
                    self.original.execution_valid(root, task, record, runner)
                    != expected
                ):
                    return [
                        "Checklist: execution receipt or policy changed during derivation"
                    ]
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            return ["Checklist: could not recheck current inputs: " + str(exc)]
        return []


def results(api, root, task):
    snapshot = _EvidenceSnapshot(api)
    result = _results(snapshot.api, root, task)
    gaps = snapshot.stability_gaps()
    if gaps:
        result["blockers"].extend(gaps)
        for row in result["rows"]:
            if row["status"] == "VERIFIED":
                row.update(status="BLOCKED", actual=gaps[0])
        result["status"] = (
            "FAIL"
            if any(row["status"] == "FAIL" for row in result["rows"])
            else "BLOCKED"
        )
        result["markdown"] = render(result["rows"])
    return result


def _results(api, root, task):
    gaps = planning_gaps(api, root, task)
    if gaps:
        return {"status": "BLOCKED", "rows": [], "markdown": "", "blockers": gaps}
    if not applicable(task):
        return {"status": "PASS", "rows": [], "markdown": "", "blockers": []}
    routes = {
        item["id"]: item
        for item in api.load(api.SKILL / "references/original-rule-map.json")["rules"]
    }
    rows = []
    for entry in read_plan(api, root, task):
        try:
            status, actual, evidence = evidence_result(api, root, task, entry, routes)
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            StopIteration,
        ) as exc:
            status, actual, evidence = (
                "BLOCKED",
                "Required evidence unavailable: " + str(exc),
                [],
            )
        rows.append({**entry, "status": status, "actual": actual, "evidence": evidence})
    status = (
        "FAIL"
        if any(row["status"] == "FAIL" for row in rows)
        else "BLOCKED" if any(row["status"] != "VERIFIED" for row in rows) else "PASS"
    )
    return {"status": status, "rows": rows, "markdown": render(rows), "blockers": []}


def sync(api, root, task):
    if not task.get("checklist_plan"):
        raise ValueError("Checklist migration required; preserve the existing Markdown")
    result = results(api, root, task)
    if result["blockers"]:
        return result
    target = api.local(root, task.get("implementation_checklist"), must_exist=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and not target.read_text(encoding="utf-8-sig").startswith(
        "# 逐项落实结果\n"
    ):
        backup = target.with_name(target.stem + ".before-sync" + target.suffix)
        try:
            with backup.open("xb") as stream:
                stream.write(target.read_bytes())
        except FileExistsError:
            pass
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=target.name + ".", suffix=".tmp", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(result["markdown"].encode("utf-8"))
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return result


def final_gaps(api, root, task):
    if not applicable(task):
        return []
    result = results(api, root, task)
    gaps = list(result["blockers"])
    if gaps:
        return gaps
    try:
        if api.local(root, task.get("implementation_checklist")).read_bytes() != result[
            "markdown"
        ].encode("utf-8"):
            gaps.append(
                "Checklist: derived Markdown is stale or edited; run checklist-sync"
            )
    except (OSError, ValueError) as exc:
        gaps.append("Checklist: result report missing: " + str(exc))
    gaps.extend(
        "Checklist: " + row["id"] + " " + row["status"] + " " + row["actual"]
        for row in result["rows"]
        if row["status"] != "VERIFIED"
    )
    return gaps
