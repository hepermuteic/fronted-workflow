"""Critic isolation, score bounds, actual-output binding and stale-result guards."""

import base64
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_delivery_review as review_tests
from test_release import p


class CriticTests(unittest.TestCase):
    def setUp(self):
        self.case = review_tests.DeliveryReviewTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.root
        self.task = {**self.case.task, "visual": True}
        p.save(self.root / p.TASK_PATH, self.task)
        self.api = SimpleNamespace(**vars(p))
        self.image = self.root / "screen.png"
        self.image.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/58HAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
            )
        )
        self.score = 9
        self.mutate = None
        self.extra_item = None
        self.process_error = None
        self.args = None
        self.stdin_text = None
        self.binding_patch = patch.object(
            p.critic, "binding", side_effect=self.current_binding
        )
        self.binding_patch.start()
        self.addCleanup(self.binding_patch.stop)

    def assessment(self):
        return {
            "score": self.score,
            "aesthetic": "Synthetic typography-led diagnostic fixture",
            "summary": "The fixture makes hierarchy and material relationships inspectable",
            "largest_gaps": [
                {
                    "image": 1,
                    "region": "Main text group",
                    "observation": "The support text has equal weight to the heading",
                    "impact": "The primary reading order loses clarity",
                    "change": "Reduce support weight and tighten its relationship to the heading",
                }
            ],
            "details": [],
            "ai_patterns": [],
            "strengths": ["The fixture has a specific visual focus"],
            "limitations": [
                "Synthetic process fixture; no actual aesthetic certification"
            ],
        }

    def current_binding(self, api, root, task):
        return {
            "task_id": task["task_id"],
            "policy_hash": api.policy_hash(),
            "contract_hash": api.contract_hash(task),
            "source_hashes": api.hashes(root, task),
            "images": [
                {
                    "capture": "snapshot.json",
                    "screenshot": "screen.png",
                    "sha256": p.sha(self.image),
                }
            ],
            "prompt_sha256": hashlib.sha256(
                p.critic.specification()["developer_instructions"].encode("utf-8")
            ).hexdigest(),
        }

    def process(self, args, **kwargs):
        owner = self
        self.args = args
        output = Path(args[args.index("--output-last-message") + 1])

        class Process:
            pid = 7654
            returncode = 0
            killed = False

            def communicate(self, text=None, timeout=None):
                owner.stdin_text = text
                if self.killed:
                    return None, None
                if owner.process_error:
                    raise owner.process_error
                if owner.mutate:
                    owner.mutate()
                raw = json.dumps(owner.assessment(), ensure_ascii=False)
                output.write_text(raw, encoding="utf-8")
                events = [
                    {"type": "thread.started", "thread_id": "synthetic-fresh-thread"},
                    {"type": "turn.started"},
                ]
                if owner.extra_item:
                    events.append({"type": "item.completed", "item": owner.extra_item})
                events.extend(
                    [
                        {
                            "type": "item.completed",
                            "item": {"type": "agent_message", "text": raw},
                        },
                        {"type": "turn.completed"},
                    ]
                )
                kwargs["stdout"].write(
                    "\n".join(json.dumps(item) for item in events) + "\n"
                )
                kwargs["stdout"].flush()
                return None, None

            def kill(self):
                self.killed = True

        return Process()

    def run_critic(self):
        with patch.object(p.critic.subprocess, "Popen", side_effect=self.process):
            return p.critic.run(self.api, self.root, self.task, cli="fixture-codex.exe")

    def next_revision(self):
        path = self.root / "helper.py"
        path.write_text(path.read_text() + "\n# revised fixture\n")

    def latest(self):
        return self.root / p.critic.report_path(self.task)

    def test_nine_accepts_critic_stage_and_keeps_delivery_pending(self):
        result = self.run_critic()
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "PASS"
        )
        self.assertEqual(p.load(self.root / p.RESULT_PATH)["status"], "BLOCKED")
        report = p.load(self.latest())
        self.assertTrue(
            (self.latest().parent / report["round_id"] / "report.json").is_file()
        )

    def test_fractional_score_is_not_rounded_up(self):
        self.score = 8.99
        self.assertEqual(self.run_critic()["status"], "FAIL")
        self.assertEqual(p.critic.check(self.api, self.root, self.task)["score"], 8.99)
        self.assertEqual(p.load(self.root / p.RESULT_PATH)["status"], "FAIL")

    def test_same_revision_reuses_score_without_process_or_record_mutation(self):
        first = self.run_critic()
        before = self.latest().read_bytes()
        p.save(self.root / p.RESULT_PATH, {'status': 'PASS', 'scope': 'Test sentinel'})
        saved_result = (self.root / p.RESULT_PATH).read_bytes()
        with patch.object(p.critic.subprocess, 'Popen', side_effect=AssertionError('Repeated model call')):
            result = p.critic.run(self.api, self.root, self.task)
        self.assertTrue(result['reused'])
        self.assertEqual(result['round_id'], first['round_id'])
        self.assertEqual(self.latest().read_bytes(), before)
        self.assertEqual((self.root / p.RESULT_PATH).read_bytes(), saved_result)

    def test_low_score_is_reused_instead_of_resampled(self):
        self.score = 6.4
        first = self.run_critic()
        self.score = 10
        with patch.object(p.critic.subprocess, 'Popen', side_effect=AssertionError('Resampled low score')):
            result = p.critic.run(self.api, self.root, self.task)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['score'], 6.4)
        self.assertEqual(result['round_id'], first['round_id'])

    def test_real_revision_creates_one_new_review(self):
        first = self.run_critic()
        self.next_revision()
        with patch.object(p.critic.subprocess, 'Popen', side_effect=self.process) as process:
            result = p.critic.run(self.api, self.root, self.task, cli='fixture-codex.exe')
        self.assertEqual(process.call_count, 1)
        self.assertNotEqual(result['round_id'], first['round_id'])

    def test_tampered_raw_reply_cannot_be_reused(self):
        self.run_critic()
        report = p.load(self.latest())
        response = self.latest().parent / report['round_id'] / 'response.json'
        response.write_text(json.dumps({**self.assessment(), 'score': 10}))
        self.process_error = RuntimeError('No valid new execution')
        with self.assertRaises(RuntimeError):
            self.run_critic()
        self.assertEqual(p.critic.check(self.api, self.root, self.task)['status'], 'BLOCKED')

    def test_missing_or_handwritten_score_is_blocked(self):
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )
        p.save(self.latest(), {"status": "SCORED", "assessment": self.assessment()})
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_actual_response_and_receipt_cannot_be_relabelled(self):
        self.run_critic()
        report = p.load(self.latest())
        report["assessment"]["score"] = 10
        p.save(self.latest(), report)
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_old_high_score_cannot_replace_a_new_lower_score(self):
        self.run_critic()
        old = p.load(self.latest())
        self.next_revision()
        self.score = 8
        self.run_critic()
        p.save(self.latest(), old)
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_prompt_cannot_be_softened_between_iterations(self):
        self.run_critic()
        spec = p.critic.specification()
        changed = {
            **spec,
            "developer_instructions": spec["developer_instructions"]
            + "A different instruction.\n",
        }
        with patch.object(p.critic, "specification", return_value=changed):
            with self.assertRaisesRegex(ValueError, "fixed Critic prompt changed"):
                self.run_critic()
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_changed_actual_reply_invalidates_current_review(self):
        self.run_critic()
        report = p.load(self.latest())
        path = self.latest().parent / report["round_id"] / "response.json"
        path.write_text(
            json.dumps({**self.assessment(), "score": 10}), encoding="utf-8"
        )
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_changed_source_and_image_invalidate_review(self):
        self.run_critic()
        (self.root / "helper.py").write_text("count = 2\n")
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )
        self.run_critic()
        self.image.write_bytes(self.image.read_bytes() + b"changed")
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_failed_new_round_invalidates_old_grade_and_saved_pass(self):
        self.run_critic()
        p.save(self.root / p.RESULT_PATH, {"status": "PASS"})
        self.next_revision()
        self.process_error = RuntimeError("Synthetic process failure")
        with self.assertRaises(RuntimeError):
            self.run_critic()
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )
        self.assertEqual(p.load(self.root / p.RESULT_PATH)["status"], "BLOCKED")

    def test_interruption_keeps_pending_state(self):
        self.run_critic()
        self.next_revision()
        self.process_error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_critic()
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )
        self.assertEqual(p.load(self.root / p.RESULT_PATH)["status"], "BLOCKED")
        self.process_error = None
        self.assertEqual(self.run_critic()["status"], "PASS")

    def test_same_task_concurrent_review_cannot_replace_an_active_round(self):
        started = threading.Event()
        release = threading.Event()
        results = []
        errors = []

        def blocking_process(args, **kwargs):
            process = self.process(args, **kwargs)
            communicate = process.communicate

            def wait_for_release(text=None, timeout=None):
                started.set()
                if not release.wait(10):
                    raise RuntimeError("Synthetic process was not released")
                return communicate(text, timeout)

            process.communicate = wait_for_release
            return process

        def review():
            try:
                results.append(
                    p.critic.run(
                        self.api, self.root, self.task, cli="fixture-codex.exe"
                    )
                )
            except BaseException as exc:
                errors.append(exc)

        with patch.object(p.critic.subprocess, "Popen", side_effect=blocking_process):
            worker = threading.Thread(target=review)
            worker.start()
            try:
                self.assertTrue(started.wait(5))
                active = p.load(self.latest())
                with self.assertRaisesRegex(ValueError, "already running"):
                    p.critic.run(
                        self.api, self.root, self.task, cli="fixture-codex.exe"
                    )
                self.assertEqual(p.load(self.latest()), active)
            finally:
                release.set()
                worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(results[0]["status"], "PASS")
        self.next_revision()
        self.score = 8
        self.assertEqual(self.run_critic()["status"], "FAIL")
        self.assertEqual(p.critic.check(self.api, self.root, self.task)["score"], 8)

    def test_lock_is_visible_to_a_separate_process(self):
        script = """import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
import critic
try:
    with critic.task_lock(SimpleNamespace(CENTER=Path(sys.argv[2])),{'task_id':sys.argv[3]}):
        print('acquired')
except ValueError:
    print('locked')
"""
        command = [
            sys.executable,
            "-c",
            script,
            str(Path(p.__file__).parent),
            str(self.api.CENTER),
            self.task["task_id"],
        ]
        with p.critic.task_lock(self.api, self.task):
            blocked = subprocess.run(
                command, capture_output=True, text=True, check=True
            )
        acquired = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(blocked.stdout.strip(), "locked")
        self.assertEqual(acquired.stdout.strip(), "acquired")

    def test_replaced_task_result_survives_an_older_review_failure(self):
        owner = "f" * 32
        expected = {
            "status": "PASS",
            "task_id": owner,
            "scope": "Synthetic newer-task result sentinel",
        }

        def replace_task():
            p.save(self.root / p.TASK_PATH, {**self.task, "task_id": owner})
            p.save(self.root / p.RESULT_PATH, expected)

        self.mutate = replace_task
        with self.assertRaises(ValueError):
            self.run_critic()
        self.assertEqual(p.load(self.root / p.RESULT_PATH), expected)

    def test_concurrent_cli_does_not_write_the_active_review_result(self):
        self.run_critic()
        result = {
            "schema": 2,
            "stage": "critic",
            "status": "BLOCKED",
            "task_id": self.task["task_id"],
            "blockers": ["Active review in progress"],
        }
        p.save(self.root / p.RESULT_PATH, result)
        latest = p.load(self.latest())
        index = p.load(p.critic.index_path(self.api, self.task))
        output = StringIO()
        with p.critic.task_lock(self.api, self.task):
            with patch.object(
                p.sys, "argv", ["verify.py", "critic-run", "--root", str(self.root)]
            ):
                with redirect_stdout(output):
                    code = p.main()
        self.assertEqual(code, 2, output.getvalue())
        self.assertIn("already running", output.getvalue())
        self.assertEqual(p.load(self.root / p.RESULT_PATH), result)
        self.assertEqual(p.load(self.latest()), latest)
        self.assertEqual(p.load(p.critic.index_path(self.api, self.task)), index)

    def test_task_change_during_review_is_blocked(self):
        self.mutate = lambda: p.save(
            self.root / p.TASK_PATH,
            {**self.task, "summary": "Changed during model call"},
        )
        with self.assertRaises(ValueError):
            self.run_critic()
        self.assertEqual(p.load(self.latest())["status"], "BLOCKED")

    def test_source_change_during_review_is_blocked(self):
        self.mutate = lambda: (self.root / "helper.py").write_text("count = 2\n")
        with self.assertRaises(ValueError):
            self.run_critic()

    def test_extra_tool_use_cannot_qualify(self):
        self.extra_item = {"type": "command_execution", "command": "read project files"}
        with self.assertRaises(ValueError):
            self.run_critic()
        self.assertEqual(
            p.critic.check(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_input_contains_only_images_and_fixed_neutral_prompt(self):
        self.run_critic()
        spec = p.critic.specification()
        self.assertEqual(self.stdin_text, p.critic.REQUEST)
        self.assertIn("--ephemeral", self.args)
        self.assertIn('model_reasoning_effort="high"', self.args)
        self.assertIn("project_doc_max_bytes=0", self.args)
        self.assertIn(
            "developer_instructions="
            + json.dumps(spec["developer_instructions"], ensure_ascii=False),
            self.args,
        )
        self.assertNotIn("9", spec["developer_instructions"])
        folder = Path(self.args[self.args.index("-C") + 1])
        self.assertEqual([item.name for item in folder.iterdir()], ["01.png"])
        self.assertEqual(self.args[self.args.index("--model") + 1], "gpt-6.1-terra")

    def test_invalid_numeric_scores_are_blocked(self):
        for score in (None, True, float("nan"), float("inf"), -1, 11):
            with self.subTest(score=score):
                self.score = score
                with self.assertRaises(ValueError):
                    p.critic.parse_report(json.dumps(self.assessment()))

    def test_nonvisual_and_reference_tasks_remain_scoped(self):
        for task in (
            {**self.task, "visual": False},
            {**self.task, "phase": "reference"},
        ):
            self.assertEqual(
                p.critic.check(self.api, self.root, task)["status"], "NOT_REQUIRED"
            )

    def test_source_bundle_requires_real_browser_receipt(self):
        self.binding_patch.stop()
        self.task["checks"].append(
            {"id": "browser", "type": "browser", "required": True}
        )
        p.save(
            self.root / "browser.json",
            {
                "type": "browser",
                "task_id": self.task["task_id"],
                "source_hashes": p.hashes(self.root, self.task),
                "captures": [],
            },
        )
        self.task["evidence"]["browser"] = "browser.json"
        with self.assertRaises(ValueError):
            p.critic.source_bundle(self.api, self.root, self.task)

    def test_frozen_approval_material_includes_actual_critic_records(self):
        self.run_critic()
        before = p.delivery_review.binding(self.api, self.root, self.task)
        self.assertIn(p.critic.report_path(self.task), before["evidence_hashes"])
        self.next_revision()
        self.score = 8
        self.run_critic()
        self.assertNotEqual(
            before, p.delivery_review.binding(self.api, self.root, self.task)
        )

    def browser_evidence(self, include_error=True, region=None):
        self.binding_patch.stop()
        self.task["scope"] = [
            {"page": "main", "width": 390, "state": state}
            for state in ("default", "error")
        ]
        if region:
            for view in self.task["scope"]:
                view["root_selector"] = region
        self.task["checks"].append(
            {"id": "browser", "type": "browser", "required": True}
        )
        p.save(self.root / p.TASK_PATH, self.task)
        captures = []
        for state in ("default", "error") if include_error else ("default",):
            name = state + "-snapshot.json"
            snapshot = {
                "schema": "frontend-policy/browser-v1",
                "source_hashes": p.hashes(self.root, self.task),
                "page": "main",
                "viewport": {"width": 390},
                "state": state,
                "screenshot": "screen.png",
                "root_selector": region or "body",
            }
            if region:
                (self.root / "region.png").write_bytes(self.image.read_bytes())
                snapshot["region_screenshot"] = "region.png"
            p.save(
                self.root / name,
                snapshot,
            )
            captures.append(name)
        record = p.record(
            self.root, self.task, "browser", {"captures": captures, "status": "PASS"}
        )
        p.seal_execution(self.root, self.task, record, "fixed-browser-process", 1234)

    def test_scope_coverage_deduplicates_identical_current_screenshots(self):
        self.browser_evidence()
        sources, artifacts, images = p.critic.source_bundle(
            self.api, self.root, self.task
        )
        self.assertEqual(sources, p.hashes(self.root, self.task))
        self.assertEqual(len(images), 1)
        self.assertIn("default-snapshot.json", artifacts)
        self.assertIn("error-snapshot.json", artifacts)

    def test_missing_declared_state_cannot_be_hidden_from_review(self):
        self.browser_evidence(include_error=False)
        with self.assertRaisesRegex(ValueError, "coverage missing"):
            p.critic.source_bundle(self.api, self.root, self.task)

    def test_component_scope_uses_its_bound_region_capture(self):
        self.browser_evidence(region="#target")
        sources, artifacts, images = p.critic.source_bundle(
            self.api, self.root, self.task
        )
        self.assertEqual(images[0]["screenshot"], "region.png")
        record = p.load(self.root / self.task["evidence"]["browser"])
        self.assertIn("screen.png", record["artifact_hashes"])
        self.assertIn("region.png", record["artifact_hashes"])

    def test_score_cannot_override_actual_command_failure(self):
        (self.root / "helper.py").write_text("count = (\n")
        p.run_check(self.root, "project-check", self.case.command)
        self.task = p.load(self.root / p.TASK_PATH)
        self.run_critic()
        result = p.verify(self.root)
        self.assertEqual(result["status"], "FAIL", result)
        self.assertTrue(any("command failed" in item for item in result["failures"]))

    def test_protected_approval_payload_binds_critic_outputs(self):
        for name in ("packet.json", "independent.json"):
            p.save(self.root / name, {})
        self.task["independent_review"] = {
            "packet": "packet.json",
            "report": "independent.json",
        }
        p.save(self.root / p.TASK_PATH, self.task)
        self.run_critic()
        p.save(
            self.root / p.delivery_review.report_path(self.task),
            {"status": "BLOCKED", "reason": "Synthetic final-review fixture"},
        )
        packet = {
            "packet_id": "fixture",
            "captures": [{"source_matches": True}],
            "files": [],
        }
        with patch.object(p.review_packet, "validate", return_value=packet):
            before = p.visual_approval.request_body(self.api, self.root, self.task)
            self.assertIn(p.critic.report_path(self.task), before["evidence_hashes"])
            self.next_revision()
            self.score = 8
            self.run_critic()
            self.assertNotEqual(
                before, p.visual_approval.request_body(self.api, self.root, self.task)
            )

    def test_cli_failure_writes_state_only_while_owning_the_lock(self):
        self.process_error = RuntimeError("Synthetic model process failure")
        original = p.critic.write_result
        ownership = []

        def write_owned(api, root, task, result):
            try:
                with p.critic.task_lock(api, task):
                    ownership.append(False)
            except p.critic.ReviewInProgress:
                ownership.append(True)
            return original(api, root, task, result)

        output = StringIO()
        with patch.object(
            p.sys, "argv", ["verify.py", "critic-run", "--root", str(self.root)]
        ):
            with patch.object(p.critic.subprocess, "Popen", side_effect=self.process):
                with patch.object(p.critic, "write_result", side_effect=write_owned):
                    with redirect_stdout(output):
                        code = p.main()
        self.assertEqual(code, 2, output.getvalue())
        self.assertTrue(ownership)
        self.assertTrue(all(ownership), ownership)
        self.assertEqual(p.load(self.root / p.RESULT_PATH)["status"], "BLOCKED")

    def test_unreadable_task_before_critic_start_clears_saved_pass(self):
        p.save(self.root / p.RESULT_PATH, {"status": "PASS"})
        (self.root / p.TASK_PATH).write_text("{invalid")
        output = StringIO()
        with patch.object(
            p.sys, "argv", ["verify.py", "critic-run", "--root", str(self.root)]
        ):
            with redirect_stdout(output):
                code = p.main()
        self.assertEqual(code, 2, output.getvalue())
        self.assertEqual(p.load(self.root / p.RESULT_PATH)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
