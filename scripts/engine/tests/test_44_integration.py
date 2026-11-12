"""Exercise checklist integration through fixed browser execution and CLI sync."""

from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_release import p, plan


class ChecklistIntegration44Tests(unittest.TestCase):
    def test_normal_browser_and_sync_preserve_execution_receipt(self):
        with tempfile.TemporaryDirectory(prefix="frontend-44-integration-") as folder:
            root = Path(folder)
            (root / "index.html").write_text(
                '<style>html{font-family:Arial,SimSun,serif}body,input,button,textarea,select{font-family:inherit}body{background:linear-gradient(20deg,#f4f1e7,#ede8dc);min-height:100vh}#copy{font-size:17px}</style><p id="copy">Readable practice instruction</p>'
            )
            task = plan(root)
            assertion = {
                "action": "expect_css_number",
                "selector": "#copy",
                "property": "fontSize",
                "min": 17,
            }
            verification = {
                "page": "main",
                "width": 390,
                "state": "default",
                "assertion": assertion,
            }
            task["project_requirements"] = [
                {
                    "id": "readable-copy",
                    "source": "design.md",
                    "expected": "Instruction uses the planned readable size",
                    "implementation": ["index.html"],
                    "verification": {"mode": "browser", **verification},
                }
            ]
            task["checklist_plan"] = "checklist-plan.json"
            task["implementation_checklist"] = "results.md"
            p.save(
                root / "checklist-plan.json",
                {
                    "schema": 1,
                    "entries": [
                        {
                            "id": "project:readable-copy",
                            "decision": "Keep the instruction readable at the narrow viewport",
                            "condition": "Instruction text is at least 17px at the declared viewport",
                            "implementation": ["index.html"],
                            "verification": {"check_id": "browser", **verification},
                        }
                    ],
                },
            )
            p.save(root / p.TASK_PATH, task)
            self.assertEqual(
                p.preflight_check(root, task, issue=True)["status"], "PASS"
            )
            p.save(
                root / "spec.json",
                {
                    "cases": [
                        {
                            "page": "main",
                            "width": 390,
                            "state": "default",
                            "url": (root / "index.html").as_uri(),
                            "steps": [assertion],
                        }
                    ]
                },
            )
            record = p.run_browser(root, "spec.json")
            self.assertEqual(record["status"], "PASS", record)
            task = p.load(root / p.TASK_PATH)
            before = p.hashes(root, task)
            process = subprocess.run(
                [
                    sys.executable,
                    str(Path(p.__file__)),
                    "checklist-sync",
                    "--root",
                    str(root),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertEqual(before, p.hashes(root, task))
            self.assertTrue(
                p.execution_valid(root, task, record, "fixed-browser-process")
            )
            self.assertEqual(
                p.checklist.final_gaps(SimpleNamespace(**vars(p)), root, task), []
            )
            self.assertIn("VERIFIED", (root / "results.md").read_text(encoding="utf-8"))
            (root / "results.md").write_text("All checks passed")
            self.assertTrue(
                p.checklist.final_gaps(SimpleNamespace(**vars(p)), root, task)
            )
            plan_data = p.load(root / "checklist-plan.json")
            plan_data["entries"][0]["condition"] = "The planned size is now 18px"
            p.save(root / "checklist-plan.json", plan_data)
            self.assertNotEqual(before, p.hashes(root, task))
            self.assertTrue(
                p.preflight.receipt_gaps(SimpleNamespace(**vars(p)), root, task)
            )

    def test_legacy_checklist_still_uses_full_source_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "index.html").write_text("Fixture")
            task = plan(root)
            task["implementation_checklist"] = "legacy.md"
            (root / "legacy.md").write_text("Original user checklist")
            before = p.hashes(root, task)
            (root / "legacy.md").write_text("Changed legacy plan")
            self.assertNotEqual(before, p.hashes(root, task))

    def test_approval_request_binds_derived_checklist_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "index.html").write_text("Fixture")
            task = plan(root)
            task.update(
                checklist_plan="plan.json",
                implementation_checklist="results.md",
                independent_review={"packet": "packet.json", "report": "report.json"},
            )
            p.save(root / "plan.json", {"schema": 1, "entries": []})
            for name in ("packet.json", "report.json"):
                p.save(root / name, {})
            (root / "results.md").write_text("Frozen results fixture")
            p.save(root / p.delivery_review.report_path(task), {"fixture": "Final review artifact byte-binding test"})
            packet = {
                "packet_id": "fixture",
                "captures": [{"source_matches": True}],
                "files": [],
            }
            with patch.object(p.review_packet, "validate", return_value=packet):
                before = p.visual_approval.request_body(
                    SimpleNamespace(**vars(p)), root, task
                )
                self.assertIn("results.md", before["evidence_hashes"])
                self.assertTrue(
                    any(
                        item["path"] == "review/checklist.md"
                        for item in before["review_files"]
                    )
                )
                (root / "results.md").write_text("Changed results fixture")
                self.assertNotEqual(
                    before,
                    p.visual_approval.request_body(
                        SimpleNamespace(**vars(p)), root, task
                    ),
                )


if __name__ == "__main__":
    unittest.main()
