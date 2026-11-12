"""Check per-item derivation. Receipt cryptography is covered by runner tests."""

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from test_release import p
import checklist


class Checklist44Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="frontend-checklist-44-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "index.html").write_text('<button id="go">Practice</button>')
        self.task = {
            "task_id": "fixture",
            "phase": "implementation",
            "level": "L2",
            "files": ["index.html"],
            "checks": [
                {"id": "browser", "type": "browser"},
                {"id": "visual", "type": "review"},
            ],
            "rule_application": [],
            "project_requirements": [{"id": "practice"}],
            "checklist_plan": "plan.json",
            "implementation_checklist": "results.md",
            "evidence": {},
        }
        self.api = SimpleNamespace(
            load=p.load,
            save=p.save,
            local=p.local,
            sha=p.sha,
            SKILL=p.SKILL,
            input_paths=p.input_paths,
            hashes=lambda root, task, include_runtime=True: {
                "index.html": p.sha(root / "index.html")
            },
            execution_valid=lambda root, task, record, runner: record.get(
                "execution_receipt"
            )
            == "valid",
            source_findings=lambda root, task: [],
        )
        self.entry = {
            "id": "project:practice",
            "decision": "Expose the next practice task",
            "implementation": ["index.html"],
            "condition": "The practice button is visible at the declared viewport",
            "verification": {
                "check_id": "browser",
                "page": "main",
                "width": 390,
                "state": "default",
                "assertion": {"action": "expect_visible", "selector": "#go"},
            },
        }
        self.write_plan()

    def write_plan(self):
        p.save(self.root / "plan.json", {"schema": 1, "entries": [self.entry]})

    def browser_record(self, **changes):
        record = {
            "task_id": "fixture",
            "type": "browser",
            "status": "PASS",
            "source_hashes": self.api.hashes(self.root, self.task),
            "artifact_hashes": {},
            "execution_receipt": "valid",
            "assertions": [
                {
                    "page": "main",
                    "width": 390,
                    "state": "default",
                    "checks": [{"action": "expect_visible", "selector": "#go"}],
                }
            ],
            **changes,
        }
        p.save(self.root / "browser.json", record)
        self.task["evidence"]["browser"] = "browser.json"
        return record

    def test_absent_record_is_blocked_and_report_remains_honest(self):
        result = checklist.sync(self.api, self.root, self.task)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("BLOCKED", (self.root / "results.md").read_text(encoding="utf-8"))
        self.assertTrue(checklist.final_gaps(self.api, self.root, self.task))

    def test_exact_actual_assertion_creates_current_report(self):
        self.browser_record()
        result = checklist.sync(self.api, self.root, self.task)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(checklist.final_gaps(self.api, self.root, self.task), [])
        self.assertIn("#go", result["rows"][0]["actual"])

    def test_missing_receipt_and_wrong_assertion_are_blocked(self):
        self.browser_record(execution_receipt="self-written")
        self.assertEqual(
            checklist.results(self.api, self.root, self.task)["status"], "BLOCKED"
        )
        self.browser_record(
            assertions=[
                {
                    "page": "main",
                    "width": 390,
                    "state": "default",
                    "checks": [{"action": "expect_visible", "selector": "#wrong"}],
                }
            ]
        )
        self.assertEqual(
            checklist.results(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_source_change_and_artifact_change_invalidate_row(self):
        self.browser_record()
        (self.root / "index.html").write_text("Changed source")
        self.assertEqual(
            checklist.results(self.api, self.root, self.task)["status"], "BLOCKED"
        )
        (self.root / "screen.png").write_bytes(b"actual fixture bytes")
        self.browser_record(artifact_hashes={"screen.png": "wrong"})
        self.assertEqual(
            checklist.results(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_known_execution_failure_remains_fail(self):
        self.browser_record(status="FAIL", runner_error="Practice action failed")
        result = checklist.results(self.api, self.root, self.task)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Practice action failed", result["rows"][0]["actual"])

    def test_edited_markdown_cannot_override_current_result(self):
        self.browser_record()
        checklist.sync(self.api, self.root, self.task)
        (self.root / "results.md").write_text("Everything PASS")
        self.assertTrue(
            any(
                "stale or edited" in gap
                for gap in checklist.final_gaps(self.api, self.root, self.task)
            )
        )
        self.entry["condition"] = "The task opens and reports a completed state"
        self.write_plan()
        self.assertTrue(checklist.final_gaps(self.api, self.root, self.task))

    def test_plan_covers_requirements_and_rejects_generic_decisions(self):
        self.entry["decision"] = "已验证"
        self.write_plan()
        self.assertTrue(checklist.planning_gaps(self.api, self.root, self.task))
        p.save(self.root / "plan.json", {"schema": 1, "entries": []})
        self.assertTrue(
            any(
                "missing planned requirement" in gap
                for gap in checklist.planning_gaps(self.api, self.root, self.task)
            )
        )

    def test_legacy_report_is_preserved_until_explicit_migration(self):
        self.task.pop("checklist_plan")
        self.task["level"] = "L3"
        (self.root / "results.md").write_text("User legacy material")
        self.assertTrue(checklist.planning_gaps(self.api, self.root, self.task))
        with self.assertRaises(ValueError):
            checklist.sync(self.api, self.root, self.task)
        self.assertEqual((self.root / "results.md").read_text(), "User legacy material")

    def test_device_method_and_specific_review_observation_are_required(self):
        self.entry["verification"] = {
            "check_id": "visual",
            "criterion": "project:practice",
            "method": "real_touch",
        }
        self.write_plan()
        (self.root / "device.txt").write_text("Fixture device session trace")
        observation = {
            "criterion": "project:practice",
            "location": "Practice control on device",
            "observed": "Tap opened the next task and retained the current selection",
            "status": "PASS",
            "evidence": ["device.txt"],
        }
        record = {
            "task_id": "fixture",
            "type": "review",
            "source_hashes": self.api.hashes(self.root, self.task),
            "artifact_hashes": {"device.txt": p.sha(self.root / "device.txt")},
            "observations": [observation],
        }
        self.task["evidence"]["visual"] = "review.json"
        p.save(self.root / "review.json", record)
        self.assertEqual(
            checklist.results(self.api, self.root, self.task)["status"], "BLOCKED"
        )
        observation["method"] = "real_touch"
        p.save(self.root / "review.json", record)
        self.assertEqual(
            checklist.results(self.api, self.root, self.task)["status"], "BLOCKED"
        )
        observation["verification_details"] = {
            "environment": "Synthetic device environment fixture",
            "tool": "Synthetic fixture touch session",
            "coverage": "Practice control and its result only",
            "steps": ["Tap practice control", "Observe the next task"],
            "expected": "Next task opens",
            "actual": "Next task opened and retained selection",
        }
        p.save(self.root / "review.json", record)
        self.assertEqual(
            checklist.results(self.api, self.root, self.task)["status"], "PASS"
        )
        observation["observed"] = "已验证"
        p.save(self.root / "review.json", record)
        self.assertEqual(
            checklist.results(self.api, self.root, self.task)["status"], "BLOCKED"
        )

    def test_report_cannot_overwrite_a_source_or_plan(self):
        for name in ("index.html", "plan.json", "./plan.json"):
            self.task["implementation_checklist"] = name
            self.assertTrue(
                checklist.planning_gaps(self.api, self.root, self.task), name
            )

    def test_browser_case_does_not_establish_real_device_method(self):
        self.entry["verification"]["method"] = "real_touch"
        self.write_plan()
        self.browser_record()
        self.assertTrue(checklist.planning_gaps(self.api, self.root, self.task))

    def test_report_cannot_overwrite_style_sources_or_library_docs(self):
        self.task.update(
            style_contract={"path": "style-source.md"},
            style_summary="style-summary.md",
            component_libraries={"items": [{"docs_evidence": "library-docs.md"}]},
        )
        for name in ("style-source.md", "style-summary.md", "library-docs.md"):
            (self.root / name).write_text("Original source material")
            self.task["implementation_checklist"] = name
            self.assertTrue(checklist.planning_gaps(self.api, self.root, self.task))
            self.assertEqual((self.root / name).read_text(), "Original source material")

    def test_first_sync_preserves_existing_user_markdown(self):
        (self.root / "results.md").write_text(
            "User notes and original planning decisions"
        )
        self.browser_record()
        checklist.sync(self.api, self.root, self.task)
        self.assertEqual(
            (self.root / "results.before-sync.md").read_text(),
            "User notes and original planning decisions",
        )
        checklist.sync(self.api, self.root, self.task)
        self.assertEqual(
            (self.root / "results.before-sync.md").read_text(),
            "User notes and original planning decisions",
        )


if __name__ == "__main__":
    unittest.main()
