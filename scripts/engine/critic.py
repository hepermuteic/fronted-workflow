"""Run the screenshot-only Critic in a fresh, isolated Codex context."""

import hashlib
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

import paths

AGENT_FILE = paths.critic_config()
MODEL = "gpt-6.1-terra"
EFFORT = "high"
MIN_SCORE = 9
REQUEST = "请评审附图。"


class ReviewInProgress(ValueError):
    """This caller did not acquire ownership of the active review."""


def required(task):
    return task.get("phase") == "implementation" and bool(task.get("visual"))


def read_toml(path):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    return tomllib.loads(Path(path).read_text(encoding="utf-8-sig"))


def specification():
    spec = read_toml(AGENT_FILE)
    if (
        spec.get("name") != "Critic"
        or spec.get("model") != MODEL
        or spec.get("model_reasoning_effort") != EFFORT
        or not spec.get("developer_instructions", "").strip()
    ):
        raise ValueError(
            "Critic must use its fixed instructions and requested model/effort"
        )
    for feature in (
        "shell_tool",
        "apps",
        "plugins",
        "memories",
        "request_permissions_tool",
    ):
        if spec.get("features", {}).get(feature) is not False:
            raise ValueError("Critic capability must be disabled: " + feature)
    if (
        spec.get("skills", {}).get("include_instructions") is not False
        or spec.get("skills", {}).get("bundled", {}).get("enabled") is not False
    ):
        raise ValueError("Critic must exclude automatic Skill context")
    return spec


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def report_path(task):
    identifier = str(task.get("task_id", ""))
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise ValueError("An initialized task is required for Critic")
    return "work/frontend-policy/evidence/" + identifier + "/critic/latest.json"


def index_path(api, task):
    report_path(task)
    return api.CENTER / "critic-tasks" / (task["task_id"] + ".json")


@contextmanager
def task_lock(api, task):
    path = index_path(api, task).with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ReviewInProgress(
                "A Critic review is already running for this task"
            ) from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def write_result(api, root, task, result):
    try:
        current = api.load(Path(root) / api.TASK_PATH)
        owner = current.get("task_id") if isinstance(current, dict) else None
        if (
            isinstance(owner, str)
            and re.fullmatch(r"[0-9a-f]{32}", owner)
            and owner != task["task_id"]
        ):
            return
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    api.save(Path(root) / api.RESULT_PATH, result)


def source_bundle(api, root, task):
    """Cover declared visual states and deduplicate identical image bytes."""
    current = api.hashes(root, task)
    artifacts = {}
    captures = {}
    views = {
        (view["page"], view["width"], view["state"]): view
        for view in task.get("scope", [])
    }
    for check in task.get("checks", []):
        if check.get("type") != "browser" or not check.get("required"):
            continue
        name = task.get("evidence", {}).get(check["id"])
        record = api.load(api.local(root, name))
        if (
            record.get("task_id") != task["task_id"]
            or record.get("type") != "browser"
            or record.get("source_hashes") != current
            or not api.execution_valid(root, task, record, "fixed-browser-process")
        ):
            raise ValueError("Critic needs current fixed-browser execution evidence")
        artifacts[name] = api.sha(api.local(root, name))
        for path, expected in record.get("artifact_hashes", {}).items():
            actual = api.sha(api.local(root, path))
            if actual != expected:
                raise ValueError("Browser evidence changed before Critic: " + path)
        for capture in record.get("captures", []):
            snapshot = api.load(api.local(root, capture))
            key = (snapshot["page"], snapshot["viewport"]["width"], snapshot["state"])
            image = snapshot.get("screenshot")
            region = views.get(key, {}).get("root_selector") or "body"
            if task.get("level") != "L3" and region not in ("body", "html"):
                if snapshot.get("root_selector") != region or not snapshot.get(
                    "region_screenshot"
                ):
                    raise ValueError(
                        "Critic needs a current screenshot of the declared component scope"
                    )
                image = snapshot["region_screenshot"]
            if task.get("level") == "L3" and snapshot.get("root_selector") not in (
                "body",
                "html",
            ):
                raise ValueError(
                    "Full-page Critic review cannot use a narrowed capture root"
                )
            if (
                snapshot.get("schema") != "frontend-policy/browser-v1"
                or snapshot.get("source_hashes") != current
                or capture not in record.get("artifact_hashes", {})
                or image not in record.get("artifact_hashes", {})
                or not api.image_artifact(api.local(root, image))
            ):
                raise ValueError(
                    "Critic screenshot is missing, stale or outside its browser receipt"
                )
            captures[key] = (capture, image)
    scopes = sorted(
        {(view["page"], view["width"], view["state"]) for view in task.get("scope", [])}
    )
    if not scopes:
        raise ValueError("Critic requires declared page and viewport coverage")
    selected = []
    seen = set()
    for key in scopes:
        if key not in captures:
            raise ValueError("Critic screenshot coverage missing: " + str(key))
        capture, image = captures[key]
        artifacts[capture] = api.sha(api.local(root, capture))
        artifacts[image] = api.sha(api.local(root, image))
        if artifacts[image] not in seen:
            selected.append(
                {"capture": capture, "screenshot": image, "sha256": artifacts[image]}
            )
            seen.add(artifacts[image])
    return current, artifacts, selected


def binding(api, root, task):
    spec = specification()
    sources, browser, images = source_bundle(api, root, task)
    return {
        "task_id": task["task_id"],
        "policy_hash": api.policy_hash(),
        "contract_hash": api.contract_hash(task),
        "source_hashes": sources,
        "browser_artifacts": browser,
        "images": images,
        "agent_sha256": api.sha(AGENT_FILE),
        "prompt_sha256": hashlib.sha256(
            spec["developer_instructions"].encode("utf-8")
        ).hexdigest(),
    }


def parse_report(text):
    text = text.strip()
    if text.startswith("```json\n") and text.endswith("\n```"):
        text = text[8:-4]
    report = json.loads(text)
    if not isinstance(report, dict):
        raise ValueError("Critic response must be a JSON object")
    score = report.get("score")
    if score is None:
        raise ValueError("Critic could not assess the screenshots")
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(score)
        or not 0 <= score <= 10
    ):
        raise ValueError("Critic score must be a finite number from zero to ten")
    if not all(
        isinstance(report.get(key), str) and report[key].strip()
        for key in ("aesthetic", "summary")
    ):
        raise ValueError("Critic needs a specific aesthetic assessment and summary")
    for key in ("largest_gaps", "details", "ai_patterns", "strengths", "limitations"):
        if not isinstance(report.get(key), list):
            raise ValueError("Critic report list missing: " + key)
    if score < 10 and not report["largest_gaps"]:
        raise ValueError("Critic needs concrete gaps supporting its score")
    for gap in report["largest_gaps"]:
        if (
            not isinstance(gap, dict)
            or isinstance(gap.get("image"), bool)
            or not isinstance(gap.get("image"), int)
            or gap["image"] < 1
            or not all(
                isinstance(gap.get(key), str) and gap[key].strip()
                for key in ("region", "observation", "impact", "change")
            )
        ):
            raise ValueError(
                "Critic gaps need image, region, observation, impact and a concrete change"
            )
    return report


def command(cli, spec, input_dir, images, output):
    args = [
        str(cli),
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "-C",
        str(input_dir),
        "-s",
        "read-only",
        "--model",
        MODEL,
        "--json",
        "--output-last-message",
        str(output),
    ]
    overrides = {
        "model_reasoning_effort": EFFORT,
        "developer_instructions": spec["developer_instructions"],
        "project_doc_max_bytes": 0,
        "skills.include_instructions": False,
        "skills.bundled.enabled": False,
        "agents.enabled": False,
        "web_search": "disabled",
    }
    overrides.update({"features." + name: False for name in spec["features"]})
    configuration = paths.CODEX_DIR / "config.toml"
    parent = read_toml(configuration) if configuration.is_file() else {}
    for name in parent.get("mcp_servers", {}):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Cannot isolate this MCP configuration name in the CLI")
        overrides["mcp_servers." + name + ".enabled"] = False
    provider = parent.get("model_provider")
    if parent.get("model_providers", {}).get(provider, {}).get("supports_websockets"):
        if re.fullmatch(r"[A-Za-z0-9_-]+", provider):
            overrides["model_providers." + provider + ".supports_websockets"] = False
    for key, value in overrides.items():
        args.extend(["-c", key + "=" + json.dumps(value, ensure_ascii=False)])
    for image in images:
        args.extend(["--image", str(input_dir / image)])
    return args + ["-"]


def run(api, root, task, cli=None):
    if not required(task):
        raise ValueError("Critic applies to current visual implementation tasks")
    with task_lock(api, task):
        try:
            current = check(api, root, task)
            if current['status'] in ('PASS', 'FAIL'):
                if api.load(Path(root) / api.TASK_PATH) != task:
                    raise ValueError('Task changed while reusing the current Critic review')
                report = api.load(api.local(root, report_path(task)))
                return {
                    'status': current['status'],
                    'stage': 'critic',
                    'score': current['score'],
                    'report': report_path(task),
                    'round_id': report['round_id'],
                    'reused': True,
                }
            return _run(api, Path(root).resolve(), task, cli)
        except Exception as exc:
            write_result(
                api,
                root,
                task,
                {
                    "schema": 2,
                    "status": "BLOCKED",
                    "stage": "critic",
                    "task_id": task["task_id"],
                    "blockers": [str(exc)],
                },
            )
            raise


def _run(api, root, task, cli):
    latest = api.local(root, report_path(task), must_exist=False)
    if latest in [
        api.local(root, name, must_exist=False) for name in api.input_paths(task)
    ]:
        raise ValueError("Critic output cannot overwrite registered inputs")
    round_id = uuid.uuid4().hex
    pending = {
        "schema": 1,
        "status": "BLOCKED",
        "task_id": task["task_id"],
        "reason": "Current Critic execution has not completed",
        "round_id": round_id,
    }
    task_index = index_path(api, task)
    previous = api.load(task_index) if task_index.is_file() else {}
    fixed_prompt = previous.get("prompt_sha256")
    api.save(latest, pending)
    api.save(task_index, {**pending, "root": str(root), "prompt_sha256": fixed_prompt})
    write_result(
        api,
        root,
        task,
        {
            "schema": 2,
            "status": "BLOCKED",
            "stage": "critic",
            "task_id": task["task_id"],
            "blockers": [pending["reason"]],
        },
    )
    try:
        spec = specification()
        before = binding(api, root, task)
        prompt_hash = hashlib.sha256(
            spec["developer_instructions"].encode("utf-8")
        ).hexdigest()
        if fixed_prompt is not None and fixed_prompt != prompt_hash:
            raise ValueError("The fixed Critic prompt changed during this task")
        api.save(
            task_index, {**pending, "root": str(root), "prompt_sha256": prompt_hash}
        )
        prefix = str(Path(report_path(task)).parent / round_id).replace("\\", "/")
        pending.update(round_id=round_id, execution_folder=prefix)
        api.save(latest, pending)
        folder = api.local(root, prefix, must_exist=False)
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "instructions.txt").write_bytes(
            spec["developer_instructions"].encode("utf-8")
        )
        input_dir = api.CENTER / "critic-runs" / round_id / "input"
        input_dir.mkdir(parents=True, exist_ok=False)
        images = []
        for index, image in enumerate(before["images"], 1):
            name = f"{index:02}.png"
            shutil.copyfile(api.local(root, image["screenshot"]), input_dir / name)
            images.append(name)
        binary = (
            cli
            or os.environ.get("CODEX_CLI_PATH")
            or shutil.which("codex.exe")
            or shutil.which("codex")
        )
        if not binary:
            raise ValueError("Codex executable unavailable for the isolated Critic")
        response = folder / "response.json"
        stdout = folder / "events.jsonl"
        stderr = folder / "stderr.txt"
        args = command(binary, spec, input_dir, images, response)
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("CODEX_THREAD_", "CODEX_PARENT_THREAD_"))
        }
        started = time.time()
        with stdout.open("w", encoding="utf-8") as out, stderr.open(
            "w", encoding="utf-8"
        ) as err:
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                text=True,
                encoding="utf-8",
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            try:
                process.communicate(REQUEST, timeout=300)
            except BaseException:
                process.kill()
                process.communicate()
                raise
        if process.returncode:
            raise ValueError("Critic process failed; inspect the recorded process log")
        events = [
            json.loads(line)
            for line in stdout.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if (
            not any(item.get("type") == "thread.started" for item in events)
            or not events
            or events[-1].get("type") != "turn.completed"
        ):
            raise ValueError("Critic did not complete a fresh execution")
        completed = [
            item["item"] for item in events if item.get("type") == "item.completed"
        ]
        if any(
            item.get("type") not in ("agent_message", "reasoning", "error")
            for item in completed
        ):
            raise ValueError("Critic used tools outside screenshot-only review")
        messages = [
            item.get("text")
            for item in completed
            if item.get("type") == "agent_message"
        ]
        raw = response.read_text(encoding="utf-8-sig")
        if not messages or messages[-1].strip() != raw.strip():
            raise ValueError("Critic final response differs from its execution stream")
        assessment = parse_report(raw)
        if any(gap["image"] > len(images) for gap in assessment["largest_gaps"]):
            raise ValueError("Critic referred to an image outside the current input")
        if binding(api, root, task) != before or api.load(root / api.TASK_PATH) != task:
            raise ValueError(
                "Task, screenshots, rules or source changed during Critic execution"
            )
        if any(
            api.sha(input_dir / name) != image["sha256"]
            for name, image in zip(images, before["images"])
        ):
            raise ValueError("Critic input image changed during execution")
        artifacts = {
            prefix + "/" + name: api.sha(folder / name)
            for name in (
                "response.json",
                "events.jsonl",
                "stderr.txt",
                "instructions.txt",
            )
            if (folder / name).stat().st_size
        }
        body = {
            "schema": 1,
            "status": "SCORED",
            "task_id": task["task_id"],
            "round_id": round_id,
            "binding": before,
            "model": MODEL,
            "reasoning_effort": EFFORT,
            "fresh_context": True,
            "input_names": images,
            "assessment": assessment,
            "artifact_hashes": artifacts,
            "process_id": process.pid,
            "started_at": started,
            "completed_at": time.time(),
        }
        receipt_id = uuid.uuid4().hex
        api.save(
            api.CENTER / "receipts" / (receipt_id + ".json"),
            {
                "runner": "critic-process",
                "root": str(root),
                "task_id": task["task_id"],
                "round_id": round_id,
                "record_hash": digest(body),
                "policy_hash": before["policy_hash"],
            },
        )
        sealed = {**body, "receipt": receipt_id}
        api.save(folder / "report.json", sealed)
        api.save(latest, sealed)
        api.save(
            task_index,
            {
                "root": str(root),
                "task_id": task["task_id"],
                "round_id": round_id,
                "receipt": receipt_id,
                "report_hash": digest(sealed),
                "prompt_sha256": prompt_hash,
            },
        )
        status = "PASS" if assessment["score"] >= MIN_SCORE else "FAIL"
        write_result(
            api,
            root,
            task,
            {
                "schema": 2,
                "status": "BLOCKED" if status == "PASS" else "FAIL",
                "stage": "critic",
                "task_id": task["task_id"],
                "score": assessment["score"],
                "blockers": (
                    ["Complete the current delivery checks after Critic review"]
                    if status == "PASS"
                    else []
                ),
                "failures": (
                    []
                    if status == "PASS"
                    else [
                        "Critic aesthetic score remains below the completion threshold"
                    ]
                ),
            },
        )
        return {
            "status": status,
            "stage": "critic",
            "score": assessment["score"],
            "report": report_path(task),
            "round_id": round_id,
        }
    except Exception as exc:
        api.save(latest, {**pending, "reason": str(exc)})
        raise


def artifacts(api, root, task):
    name = report_path(task)
    path = api.local(root, name, must_exist=False)
    if not path.is_file():
        return {}
    report = api.load(path)
    return {
        name: api.sha(api.local(root, name)),
        **{
            path: api.sha(api.local(root, path))
            for path in report.get("artifact_hashes", {})
        },
    }


def check(api, root, task):
    if not required(task):
        return {"status": "NOT_REQUIRED", "failures": [], "blockers": []}
    try:
        report = api.load(api.local(root, report_path(task)))
        if report.get("status") != "SCORED":
            raise ValueError(
                report.get("reason") or "Current Critic execution is incomplete"
            )
        receipt_id = report.get("receipt", "")
        if not re.fullmatch(r"[0-9a-f]{32}", receipt_id):
            raise ValueError("Actual Critic execution receipt is missing")
        body = {key: value for key, value in report.items() if key != "receipt"}
        current_round = api.load(index_path(api, task))
        if current_round != {
            "root": str(Path(root).resolve()),
            "task_id": task["task_id"],
            "round_id": report["round_id"],
            "receipt": receipt_id,
            "report_hash": digest(report),
            "prompt_sha256": report["binding"]["prompt_sha256"],
        }:
            raise ValueError("Critic report is not the latest executed review")
        receipt = api.load(api.CENTER / "receipts" / (receipt_id + ".json"))
        if receipt != {
            "runner": "critic-process",
            "root": str(Path(root).resolve()),
            "task_id": task["task_id"],
            "round_id": report["round_id"],
            "record_hash": digest(body),
            "policy_hash": api.policy_hash(),
        }:
            raise ValueError(
                "Critic record does not match its current execution receipt"
            )
        if (
            report.get("model") != MODEL
            or report.get("reasoning_effort") != EFFORT
            or report.get("fresh_context") is not True
        ):
            raise ValueError("Critic model, effort or fresh-context settings differ")
        if report.get("binding") != binding(api, root, task):
            raise ValueError(
                "Critic score is stale relative to current task, screenshots or source"
            )
        for name, expected in report.get("artifact_hashes", {}).items():
            if api.sha(api.local(root, name)) != expected:
                raise ValueError("Critic execution artifact changed: " + name)
        response = (
            report_path(task).rsplit("/", 1)[0]
            + "/"
            + report["round_id"]
            + "/response.json"
        )
        if response not in report.get("artifact_hashes", {}):
            raise ValueError("Critic response is outside the bound execution artifacts")
        instructions = response.rsplit("/", 1)[0] + "/instructions.txt"
        if (
            report.get("artifact_hashes", {}).get(instructions)
            != report["binding"]["prompt_sha256"]
        ):
            raise ValueError("Critic instructions differ from the fixed review prompt")
        assessment = parse_report(
            api.local(root, response).read_text(encoding="utf-8-sig")
        )
        if assessment != report.get("assessment"):
            raise ValueError("Recorded Critic score differs from its actual response")
        failures = (
            []
            if assessment["score"] >= MIN_SCORE
            else ["Critic: aesthetic score below the completion threshold"]
        )
        return {
            "status": "PASS" if not failures else "FAIL",
            "score": assessment["score"],
            "report": report_path(task),
            "failures": failures,
            "blockers": [],
        }
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ImportError,
    ) as exc:
        return {
            "status": "BLOCKED",
            "failures": [],
            "blockers": ["Critic: " + str(exc)],
        }
