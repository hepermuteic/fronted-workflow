"""JavaScript/TypeScript edits obey the same explicit-only Hook policy."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_release import p


class FrameworkHookTests(unittest.TestCase):
    def test_script_edits_remind_and_cannot_hide_as_reference_handoff(self):
        for extension in ("js", "ts", "mjs", "mts", "cjs", "cts"):
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                event = {"session_id": "framework-" + extension, "turn_id": "1", "cwd": str(root)}
                with patch.object(p, "CENTER", root / "center"):
                    p.hook({**event, "hook_event_name": "UserPromptSubmit", "prompt": "使用 frontend-workflow 制作前端页面"})
                    reminder = p.hook({**event, "hook_event_name": "PostToolUse", "tool_input": {"file_path": "src/main." + extension}})
                    self.assertIn("hookSpecificOutput", reminder)
                    stopped = p.hook({**event, "hook_event_name": "Stop", "last_assistant_message": "四张风格参考已展示，请选择 A、B、C、D。"})
                    self.assertEqual(stopped.get("decision"), "block", stopped)

    def test_script_edits_do_not_implicitly_enable_workflow(self):
        for extension in ("js", "ts", "mjs", "mts", "cjs", "cts"):
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                event = {"session_id": "ordinary-" + extension, "turn_id": "1", "cwd": str(root)}
                with patch.object(p, "CENTER", root / "center"):
                    self.assertEqual(p.hook({**event, "hook_event_name": "UserPromptSubmit", "prompt": "修改这个 TypeScript 文件"}), {})
                    self.assertEqual(p.hook({**event, "hook_event_name": "PostToolUse", "tool_input": {"file_path": "src/main." + extension}}), {})
                    self.assertEqual(p.hook({**event, "hook_event_name": "Stop", "last_assistant_message": "文件已修改"}), {})


if __name__ == "__main__":
    unittest.main()
