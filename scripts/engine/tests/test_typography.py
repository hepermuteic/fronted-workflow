"""Actual body-font checks, including aliases and Chinese fallback."""

import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_release import p, plan


class TypographyTests(unittest.TestCase):
    def test_aliases_are_recognized(self):
        for value in (
            "Microsoft YaHei",
            "Microsoft YaHei UI",
            "微软雅黑",
            "MicrosoftYaHei-Bold",
            "Ｍｉｃｒｏｓｏｆｔ ＹａＨｅｉ",
        ):
            self.assertTrue(p.typography.is_yahei(value), value)
        for value in ("Source Han Sans SC", "Noto Sans SC", "LXGW WenKai", "Georgia"):
            self.assertFalse(p.typography.is_yahei(value), value)

    def test_inline_stylesheet_body_font_is_checked(self):
        self.assertTrue(
            p.typography.source_findings(
                '<style>body{font-family:"Microsoft YaHei"}</style>'
            )
        )

    def test_missing_actual_inspection_stays_unverified(self):
        self.assertTrue(p.typography.findings({})[1])

    def test_source_body_rule_is_rejected_without_banning_headings(self):
        self.assertTrue(
            p.typography.source_findings('body { font-family:"Microsoft YaHei"; }')
        )
        self.assertFalse(
            p.typography.source_findings('h1 { font-family:"Microsoft YaHei"; }')
        )
        self.assertFalse(
            p.typography.source_findings('body h1 { font-family:"Microsoft YaHei"; }')
        )

    def test_hidden_alias_is_detected_from_actual_glyphs(self):
        snapshot = {
            "body_typography": {
                "status": "verified",
                "errors": [],
                "samples": [
                    {
                        "selector": "p",
                        "font_family": "BodyFont",
                        "fonts": [
                            {
                                "familyName": "BodyFont",
                                "postScriptName": "MicrosoftYaHei",
                                "glyphCount": 2,
                            }
                        ],
                    }
                ],
            }
        }
        self.assertTrue(p.typography.findings(snapshot)[0])

    def browser(self, html):
        temporary = tempfile.TemporaryDirectory(prefix="frontend-font-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "index.html").write_text(
            '<meta charset="utf-8"><style>html{font-family:Arial,SimSun,serif}body,input,button,textarea,select{font-family:inherit}body{background:linear-gradient(20deg,#f4f1e7,#ede8dc);min-height:100vh}</style>'
            + html,
            encoding="utf-8",
        )
        (root / "center").mkdir()
        for name in ("browser-run.cjs", "font_capture.cjs"):
            shutil.copyfile(Path(p.__file__).parent / name, root / "center" / name)
        with patch.object(p, "CENTER", root / "center"):
            task = plan(root)
            p.save(
                root / "spec.json",
                {
                    "cases": [
                        {
                            "page": "main",
                            "width": 390,
                            "state": "default",
                            "url": (root / "index.html").as_uri(),
                            "steps": [{"action": "expect_visible", "selector": "main"}],
                        }
                    ]
                },
            )
            record = p.run_browser(root, "spec.json")
            report = (
                p.browser_findings(root, p.load(root / p.TASK_PATH), record["captures"])
                if record.get("captures")
                else {"runner_error": record.get("runner_error"), "findings": []}
            )
        return record, report

    def test_real_declared_body_stack_is_rejected(self):
        record, report = self.browser(
            '<main><p style="font-family:Microsoft YaHei">正文</p></main>'
        )
        self.assertEqual(record["status"], "FAIL", report)
        self.assertTrue(any("body font" in item for item in report["findings"]), report)

    def test_display_heading_does_not_contaminate_body_font(self):
        record, report = self.browser(
            '<main>Readable <h1 style="font-family:Microsoft YaHei">标题</h1><p>正文可读。</p></main>'
        )
        self.assertEqual(record["status"], "PASS", report)

    @unittest.skipUnless(os.name == "nt", "Actual Windows local-font regression")
    def test_real_font_face_alias_cannot_hide_yahei(self):
        record, report = self.browser(
            '<style>@font-face{font-family:BodyAlias;src:local("Microsoft YaHei")}</style><main><p style="font-family:BodyAlias">正文</p></main>'
        )
        self.assertEqual(record["status"], "FAIL", report)
        self.assertTrue(
            any("actually rendered" in item for item in report["findings"]), report
        )

    def test_controls_and_generated_copy_are_inspected(self):
        record, report = self.browser(
            '<style>#hint::before{content:"填写姓名"}</style><main><p id="hint"></p><input value="练习"><button>继续</button></main>'
        )
        self.assertEqual(record["status"], "PASS", report)

    def test_open_shadow_body_font_is_checked(self):
        record, report = self.browser(
            '<main id="host"></main><script>document.querySelector("main").attachShadow({mode:"open"}).innerHTML="<p style=\\"font-family:Microsoft YaHei\\">正文</p>"</script>'
        )
        self.assertEqual(record["status"], "FAIL", report)
        self.assertTrue(any("body font" in item for item in report["findings"]), report)


if __name__ == "__main__":
    unittest.main()
