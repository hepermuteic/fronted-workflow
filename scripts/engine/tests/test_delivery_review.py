"""Final improvement review uses current checked evidence and an actual receipt."""

from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_release import p, plan


class DeliveryReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frontend-final-review-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "index.html").write_text(
            "<main>Compiler diagnostic fixture</main>"
        )
        (self.root / "helper.py").write_text("count = 1\n")
        self.center = patch.object(p, "CENTER", self.root / "center")
        self.center.start()
        self.addCleanup(self.center.stop)
        self.task = plan(self.root, visual=False)
        self.task["files"].append("helper.py")
        self.task["visual_reason"] = (
            "Nonvisual compiler and final-review regression scope"
        )
        p.save(self.root / p.TASK_PATH, self.task)
        self.command = [
            sys.executable,
            "-c",
            "from pathlib import Path;compile(Path('helper.py').read_text(),'helper.py','exec')",
        ]
        self.run_check()

    def run_check(self):
        p.run_check(self.root, "project-check", self.command)
        self.task = p.load(self.root / p.TASK_PATH)
        self.api = SimpleNamespace(**vars(p))

    def reflection(self):
        evidence = [self.task["evidence"]["project-check"]]
        return {
            "schema": 1,
            "rounds": [
                {
                    "observations": [
                        {
                            "area": "rules",
                            "observed": "The declared nonvisual scope and current compiler evidence cover this diagnostic change",
                            "evidence": evidence,
                        },
                        {
                            "area": "quality",
                            "observed": "The current helper source compiles and the retained count has a concrete test role",
                            "evidence": evidence,
                        },
                        {
                            "area": "scope",
                            "observed": "No additional in-scope compiler or delivery defect was identified in the current fixture",
                            "evidence": evidence,
                        },
                    ],
                    "improvements": [],
                }
            ],
            "remaining_improvements": [],
            "completion_reason": "The requested diagnostic helper is compiled and no further actionable issue was identified in its declared scope",
        }

    def test_no_record_blocks_unsupported_completion(self):
        self.assertEqual(p.verify(self.root)["status"], "BLOCKED")
        self.assertTrue(
            p.delivery_review.check(self.api, self.root, self.task)["blockers"]
        )

    def test_actual_review_command_closes_current_scope(self):
        result = p.delivery_review.record(
            self.api, self.root, self.task, self.reflection()
        )
        self.assertEqual(result["status"], "READY", result)
        self.assertEqual(p.verify(self.root)["status"], "PASS")

    def test_open_improvement_requires_repair_and_recheck(self):
        reflection = self.reflection()
        finding = {
            "id": "I1",
            "issue": "The helper count needs the scoped revised value",
            "status": "open",
        }
        reflection["rounds"][0]["improvements"] = [finding]
        first = p.delivery_review.record(self.api, self.root, self.task, reflection)
        self.assertEqual(first["status"], "FAIL")
        (self.root / "helper.py").write_text("count = 2\n")
        self.run_check()
        repaired = self.reflection()["rounds"][0]
        repaired["improvements"] = [
            {
                **finding,
                "status": "resolved",
                "action": "Updated the actual helper count and reran the compiler check",
                "implementation": ["helper.py"],
                "evidence": [self.task["evidence"]["project-check"]],
            }
        ]
        reflection["rounds"].append(repaired)
        self.assertEqual(
            p.delivery_review.record(self.api, self.root, self.task, reflection)[
                "status"
            ],
            "READY",
        )
        self.assertEqual(p.verify(self.root)["status"], "PASS")

    def test_source_and_evidence_change_invalidate_last_review(self):
        p.delivery_review.record(self.api, self.root, self.task, self.reflection())
        (self.root / "helper.py").write_text("count = 3\n")
        self.assertTrue(
            p.delivery_review.check(self.api, self.root, self.task)["blockers"]
        )
        self.run_check()
        self.assertTrue(
            p.delivery_review.check(self.api, self.root, self.task)["blockers"]
        )

    def test_handwritten_ready_cannot_substitute_for_receipt(self):
        path = self.root / p.delivery_review.report_path(self.task)
        p.save(
            path,
            {
                "status": "READY",
                "binding": p.delivery_review.binding(self.api, self.root, self.task),
                "reflection": self.reflection(),
            },
        )
        self.assertTrue(
            p.delivery_review.check(self.api, self.root, self.task)["blockers"]
        )

    def test_editing_a_real_review_breaks_its_receipt(self):
        p.delivery_review.record(self.api, self.root, self.task, self.reflection())
        path = self.root / p.delivery_review.report_path(self.task)
        record = p.load(path)
        record["reflection"][
            "completion_reason"
        ] = "Altered after the actual final review"
        p.save(path, record)
        self.assertTrue(
            p.delivery_review.check(self.api, self.root, self.task)["blockers"]
        )

    def test_generic_or_unknown_evidence_cannot_close_review(self):
        reflection = self.reflection()
        reflection["rounds"][0]["observations"][0]["observed"] = "已验证"
        self.assertEqual(
            p.delivery_review.record(self.api, self.root, self.task, reflection)[
                "status"
            ],
            "BLOCKED",
        )
        reflection = self.reflection()
        reflection["rounds"][0]["observations"][0]["evidence"] = ["helper.py"]
        self.assertEqual(
            p.delivery_review.record(self.api, self.root, self.task, reflection)[
                "status"
            ],
            "BLOCKED",
        )

    def test_remaining_improvement_is_not_a_ready_review(self):
        reflection = self.reflection()
        reflection["remaining_improvements"] = ["Improve the current helper value"]
        self.assertEqual(
            p.delivery_review.record(self.api, self.root, self.task, reflection)[
                "status"
            ],
            "FAIL",
        )

    def test_failing_actual_check_cannot_be_hidden_by_empty_findings(self):
        (self.root / "helper.py").write_text("count = (\n")
        self.run_check()
        result = p.delivery_review.record(
            self.api, self.root, self.task, self.reflection()
        )
        self.assertEqual(result["status"], "FAIL", result)

    def test_registered_source_alone_does_not_prove_final_recheck(self):
        reflection = self.reflection()
        reflection["rounds"][0]["observations"][0]["evidence"] = ["helper.py"]
        source = {"helper.py": p.sha(self.root / "helper.py")}
        _, blockers = p.delivery_review.reflection_findings(
            self.api, self.root, reflection, source, source
        )
        self.assertTrue(any("current check result" in item for item in blockers))

    def test_output_path_alias_cannot_overwrite_a_planning_input(self):
        path = p.delivery_review.report_path(self.task)
        p.save(self.root / path, {"original": "Preserved planning input"})
        self.task["style_summary"] = "./" + path
        with self.assertRaisesRegex(ValueError, "separate from source"):
            p.delivery_review.record(self.api, self.root, self.task, self.reflection())
        self.assertEqual(
            p.load(self.root / path), {"original": "Preserved planning input"}
        )

    def test_approval_request_binds_the_actual_final_review(self):
        for name in ("packet.json", "independent.json"):
            p.save(self.root / name, {})
        self.task["independent_review"] = {
            "packet": "packet.json",
            "report": "independent.json",
        }
        p.save(self.root / p.TASK_PATH, self.task)
        result = p.delivery_review.record(
            self.api, self.root, self.task, self.reflection()
        )
        self.assertEqual(result["status"], "READY", result)
        packet = {
            "packet_id": "fixture",
            "captures": [{"source_matches": True}],
            "files": [],
        }
        with patch.object(p.review_packet, "validate", return_value=packet):
            before = p.visual_approval.request_body(self.api, self.root, self.task)
            path = p.delivery_review.report_path(self.task)
            self.assertIn(path, before["evidence_hashes"])
            p.save(self.root / path, {"changed": "Final report changed after binding"})
            self.assertNotEqual(
                before, p.visual_approval.request_body(self.api, self.root, self.task)
            )

    def test_failed_new_review_invalidates_previous_ready(self):
        p.delivery_review.record(self.api, self.root, self.task, self.reflection())
        (self.root / "broken-reflection.json").write_text("{invalid")
        with self.assertRaises(ValueError):
            p.delivery_review.record(
                self.api, self.root, self.task, reflection_path="broken-reflection.json"
            )
        self.assertTrue(
            p.delivery_review.check(self.api, self.root, self.task)["blockers"]
        )
        self.assertEqual(p.verify(self.root)["status"], "BLOCKED")

    def test_invalid_task_identity_cannot_select_an_output_path(self):
        task = {**self.task, "task_id": "../../outside"}
        with self.assertRaises(ValueError):
            p.delivery_review.report_path(task)

    def test_editing_the_reflection_input_requires_another_review(self):
        p.save(self.root / "reflection.json", self.reflection())
        result = p.delivery_review.record(
            self.api, self.root, self.task, reflection_path="reflection.json"
        )
        self.assertEqual(result["status"], "READY", result)
        edited = self.reflection()
        edited["remaining_improvements"] = ["A newly identified scoped issue"]
        p.save(self.root / "reflection.json", edited)
        self.assertTrue(
            p.delivery_review.check(self.api, self.root, self.task)["blockers"]
        )

    def test_cli_entry_records_real_final_review(self):
        p.save(self.root / "reflection.json", self.reflection())
        package = self.root / "cli-skill"
        shutil.copytree(p.SKILL, package, ignore=shutil.ignore_patterns('outputs', '__pycache__'))
        engine = package / "scripts/engine"
        entry = engine / "verify.py"
        initialized = subprocess.run(
            [
                sys.executable,
                entry,
                "init",
                "--root",
                str(self.root),
                "--level",
                "L1",
                "--no-visual",
                "--files",
                "helper.py",
                "--replace",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stdout)
        task = p.load(self.root / p.TASK_PATH)
        for item in task["rule_application"]:
            item.update(
                applicability="out_of_scope", reason="Controlled CLI invocation fixture"
            )
        task["checks"].append(
            {"id": "project-check", "type": "command", "required": True}
        )
        p.save(self.root / p.TASK_PATH, task)
        subprocess.run(
            [
                sys.executable,
                entry,
                "run",
                "--root",
                str(self.root),
                "--check-id",
                "project-check",
                "--",
                *self.command,
            ],
            check=True,
            capture_output=True,
        )
        self.task = p.load(self.root / p.TASK_PATH)
        p.save(self.root / "reflection.json", self.reflection())
        result = subprocess.run(
            [
                sys.executable,
                entry,
                "delivery-review",
                "--root",
                str(self.root),
                "--observations",
                "reflection.json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
