"""Batch reuse and one-pass delivery preserve evidence and approval checks."""

from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_checklist_44 as checklist_tests
import test_delivery_review as review_tests
from test_release import p


class EfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.case = review_tests.DeliveryReviewTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.root

    def batch(self, size=100):
        task = self.case.task
        task["checklist_plan"] = "checklist-plan.json"
        task["implementation_checklist"] = "checklist-results.md"
        task["project_requirements"] = [{"id": "item-" + str(i)} for i in range(size)]
        entries = [
            {
                "id": "project:item-" + str(i),
                "decision": "Check the current diagnostic helper for item " + str(i),
                "implementation": ["helper.py"],
                "condition": "The diagnostic helper compiles for item " + str(i),
                "verification": {"check_id": "project-check"},
            }
            for i in range(size)
        ]
        p.save(self.root / "checklist-plan.json", {"schema": 1, "entries": entries})
        p.save(self.root / p.TASK_PATH, task)
        self.case.run_check()
        return self.case.task

    def test_one_hundred_rows_share_reads_and_recheck_freshness(self):
        task = self.batch()
        api = SimpleNamespace(**vars(p))
        counts = Counter()
        for name in ("load", "hashes", "execution_valid"):
            original = getattr(api, name)

            def counted(*args, _name=name, _original=original, **kwargs):
                counts[_name] += 1
                return _original(*args, **kwargs)

            setattr(api, name, counted)
        result = p.checklist.results(api, self.root, task)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(len(result["rows"]), 100)
        self.assertEqual(counts["hashes"], 2)
        self.assertEqual(counts["execution_valid"], 2)
        self.assertEqual(counts["load"], 3)

    def test_source_change_during_batch_blocks_cached_rows(self):
        task = self.batch(3)
        api = SimpleNamespace(**vars(p))
        original = api.hashes
        calls = 0

        def change_after_hash(*args, **kwargs):
            nonlocal calls
            value = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                (self.root / "helper.py").write_text("count = 2\n")
            return value

        api.hashes = change_after_hash
        result = p.checklist.results(api, self.root, task)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertFalse(any(row["status"] == "VERIFIED" for row in result["rows"]))

    def test_artifact_change_during_batch_blocks_cached_rows(self):
        task = self.batch(3)
        api = SimpleNamespace(**vars(p))
        original = api.execution_valid
        record = p.load(self.root / task["evidence"]["project-check"])
        calls = 0

        def change_after_receipt(*args):
            nonlocal calls
            valid = original(*args)
            calls += 1
            if calls == 1:
                (self.root / record["log"]).write_text(
                    "Changed after initial validation"
                )
            return valid

        api.execution_valid = change_after_receipt
        result = p.checklist.results(api, self.root, task)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(result["blockers"])

    def test_receipt_change_during_batch_is_rechecked(self):
        task = self.batch(3)
        api = SimpleNamespace(**vars(p))
        api.execution_valid = Mock(side_effect=[True, False])
        result = p.checklist.results(api, self.root, task)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIn("receipt or policy changed", result["blockers"][0])

    def test_policy_change_during_batch_invalidates_reused_results(self):
        task = self.batch(3)
        api = SimpleNamespace(**vars(p))
        api.policy_hash = Mock(side_effect=["before", "after"])
        result = p.checklist.results(api, self.root, task)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIn("policy changed", result["blockers"][0])

    def test_later_invocation_reads_changed_evidence(self):
        task = self.batch(3)
        self.assertEqual(
            p.checklist.results(self.case.api, self.root, task)["status"], "PASS"
        )
        path = self.root / task["evidence"]["project-check"]
        record = p.load(path)
        record["execution_receipt"] = "self-written"
        p.save(path, record)
        self.assertEqual(
            p.checklist.results(self.case.api, self.root, task)["status"], "BLOCKED"
        )

    def test_each_row_still_needs_its_exact_assertion(self):
        case = checklist_tests.Checklist44Tests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.task["project_requirements"].append({"id": "other"})
        other = {
            **case.entry,
            "id": "project:other",
            "verification": {
                **case.entry["verification"],
                "assertion": {"action": "expect_visible", "selector": "#missing"},
            },
        }
        p.save(case.root / "plan.json", {"schema": 1, "entries": [case.entry, other]})
        case.browser_record()
        result = p.checklist.results(case.api, case.root, case.task)
        self.assertEqual(
            [row["status"] for row in result["rows"]], ["VERIFIED", "BLOCKED"]
        )

    def test_finalize_uses_one_full_validation_and_keeps_standalone_result(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        with patch.object(p, "verify", wraps=p.verify) as verification:
            with patch.object(
                p, "run_check", side_effect=AssertionError("Unnecessary rerun")
            ):
                result = p.finalize(self.root, "reflection.json")
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(verification.call_count, 1)
        standalone = p.verify(self.root)
        for key in (
            "status",
            "failures",
            "blockers",
            "automated_status",
            "visual_acceptance",
        ):
            self.assertEqual(result[key], standalone[key], key)

    def test_finalize_syncs_checklist_without_extra_manual_commands(self):
        rule = next(
            item
            for item in p.load(p.SKILL / "references/original-rule-map.json")["rules"]
            if item["method"] == "automated"
        )
        task = self.case.task
        task["checklist_plan"] = "checklist-plan.json"
        task["implementation_checklist"] = "checklist-results.md"
        for application in task["rule_application"]:
            if application["id"] == rule["id"]:
                application.update(
                    applicability="applicable",
                    reason="Current diagnostic source scan fixture",
                )
        p.save(
            self.root / "checklist-plan.json",
            {
                "schema": 1,
                "entries": [
                    {
                        "id": "rule:" + rule["id"],
                        "decision": "Scan the current diagnostic source in its declared file scope",
                        "implementation": ["helper.py"],
                        "condition": "The source scanner reports no prohibited content in current inputs",
                        "verification": {"check_id": "source"},
                    }
                ],
            },
        )
        p.save(self.root / p.TASK_PATH, task)
        self.case.run_check()
        p.save(self.root / "reflection.json", self.case.reflection())
        self.assertFalse((self.root / "checklist-results.md").exists())
        result = p.finalize(self.root, "reflection.json")
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(
            p.checklist.final_gaps(self.case.api, self.root, self.case.task), []
        )

    def test_finalize_keeps_real_failures(self):
        (self.root / "helper.py").write_text("count = (\n")
        self.case.run_check()
        p.save(self.root / "reflection.json", self.case.reflection())
        result = p.finalize(self.root, "reflection.json")
        self.assertEqual(result["status"], "FAIL", result)
        self.assertTrue(any("command failed" in item for item in result["failures"]))

    def test_finalize_checks_protected_approval_once(self):
        task = {**self.case.task, "visual": True}
        p.save(self.root / p.TASK_PATH, task)
        p.save(self.root / "reflection.json", self.case.reflection())
        with patch.object(
            p.visual_approval, "verify", wraps=p.visual_approval.verify
        ) as approval:
            result = p.finalize(self.root, "reflection.json")
        self.assertEqual(approval.call_count, 1)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertNotEqual(result["visual_acceptance"], "APPROVED")

    def test_failed_new_finalization_invalidates_previous_ready(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        self.assertEqual(p.finalize(self.root, "reflection.json")["status"], "PASS")
        (self.root / "reflection.json").write_text("{invalid")
        with self.assertRaises(ValueError):
            p.finalize(self.root, "reflection.json")
        self.assertEqual(p.verify(self.root)["status"], "BLOCKED")

    def test_finalize_cli_saves_computed_result(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        output = StringIO()
        with patch.object(
            p.sys,
            "argv",
            [
                "verify.py",
                "finalize",
                "--root",
                str(self.root),
                "--observations",
                "reflection.json",
            ],
        ):
            with redirect_stdout(output):
                code = p.main()
        self.assertEqual(code, 0, output.getvalue())
        printed = json.loads(output.getvalue())
        self.assertEqual(printed["status"], "PASS")
        self.assertEqual(p.load(self.root / p.RESULT_PATH), printed)

    def test_task_change_inside_completion_blocks_final_result(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        original = p.delivery_review.check

        def change_during_completion(api, root, task):
            changed = p.load(root / p.TASK_PATH)
            changed["summary"] = "Changed during final binding validation"
            p.save(root / p.TASK_PATH, changed)
            return original(api, root, task)

        with patch.object(
            p.delivery_review, "check", side_effect=change_during_completion
        ):
            result = p.finalize(self.root, "reflection.json")
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(any("Task plan changed" in item for item in result["blockers"]))
        self.assertEqual(p.load(self.root / p.RESULT_PATH), result)

    def test_default_verify_reconciles_task_after_completion(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        p.finalize(self.root, "reflection.json")
        original = p.delivery_review.check

        def change_during_completion(api, root, task):
            changed = p.load(root / p.TASK_PATH)
            changed["summary"] = "Changed during standalone verification"
            p.save(root / p.TASK_PATH, changed)
            return original(api, root, task)

        with patch.object(
            p.delivery_review, "check", side_effect=change_during_completion
        ):
            result = p.verify(self.root)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(any("Task plan changed" in item for item in result["blockers"]))

    def test_check_cli_reconciles_task_after_completion(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        p.finalize(self.root, "reflection.json")
        original = p.delivery_review.check

        def change_during_completion(api, root, task):
            changed = p.load(root / p.TASK_PATH)
            changed["summary"] = "Changed during check CLI completion"
            p.save(root / p.TASK_PATH, changed)
            return original(api, root, task)

        output = StringIO()
        with patch.object(
            p.sys, "argv", ["verify.py", "check", "--root", str(self.root)]
        ):
            with patch.object(
                p.delivery_review, "check", side_effect=change_during_completion
            ):
                with redirect_stdout(output):
                    code = p.main()
        self.assertEqual(code, 2, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")
        self.assertEqual(p.load(self.root / p.RESULT_PATH)["status"], "BLOCKED")

    def test_explicit_task_diagnostics_keep_stable_disk_semantics(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        p.finalize(self.root, "reflection.json")
        task = {**self.case.task, "diagnostic_note": "Read-only caller context"}
        result = p.verify(self.root, task)
        self.assertEqual(result["status"], "PASS", result)
        self.assertNotIn("diagnostic_note", p.load(self.root / p.TASK_PATH))

    def test_invalid_final_input_clears_saved_pass(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        self.assertEqual(p.finalize(self.root, "reflection.json")["status"], "PASS")
        (self.root / "reflection.json").write_text("{invalid")
        with self.assertRaises(ValueError):
            p.finalize(self.root, "reflection.json")
        result = p.load(self.root / p.RESULT_PATH)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertTrue(result["error"])

    def test_checker_error_clears_saved_pass(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        self.assertEqual(p.finalize(self.root, "reflection.json")["status"], "PASS")
        with patch.object(p, "verify", side_effect=RuntimeError("Checker interrupted")):
            with self.assertRaises(RuntimeError):
                p.finalize(self.root, "reflection.json")
        result = p.load(self.root / p.RESULT_PATH)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIn("Checker interrupted", result["error"])

    def test_process_interruption_leaves_pending_blocked_state(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        self.assertEqual(p.finalize(self.root, "reflection.json")["status"], "PASS")
        with patch.object(p, "verify", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                p.finalize(self.root, "reflection.json")
        result = p.load(self.root / p.RESULT_PATH)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIn("awaiting", result["blockers"][0])

    def test_malformed_check_collections_return_blocked(self):
        for checks in (None, "browser", {}, [None], ["browser"], [1]):
            with self.subTest(checks=checks):
                result = p.verify(self.root, {**self.case.task, "checks": checks})
                self.assertEqual(result["status"], "BLOCKED", result)
                self.assertTrue(result["blockers"])

    def test_check_and_finalize_cli_errors_clear_saved_pass(self):
        p.save(self.root / "reflection.json", self.case.reflection())
        for command in ("check", "finalize"):
            with self.subTest(command=command):
                self.assertEqual(
                    p.finalize(self.root, "reflection.json")["status"], "PASS"
                )
                output = StringIO()
                argv = [
                    "verify.py",
                    command,
                    "--root",
                    str(self.root),
                    "--observations",
                    "reflection.json",
                ]
                with patch.object(p.sys, "argv", argv):
                    with patch.object(
                        p, "verify", side_effect=RuntimeError("Checker error")
                    ):
                        with redirect_stdout(output):
                            code = p.main()
                self.assertEqual(code, 2, output.getvalue())
                self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")
                self.assertEqual(p.load(self.root / p.RESULT_PATH)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
