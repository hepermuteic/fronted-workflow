# Framework-independent implementation

- Reuse discovery results from this task when package.json, lockfiles, build scripts and the relevant project configuration are unchanged. If missing or changed, run discover, inspect those inputs and relevant source, then select actual project commands. React, Vue and plain HTML share policy and evidence format, not identical commands.
- Reuse the installed framework and component system. Keep text, UI state and assets maintainable; do not substitute a generated screenshot for live UI.
- Plan affected files, pages, states and viewports before editing. Add runtime entry points/bundles to the inspected scope when the browser loads them; source-only checks do not cover bundled dependencies automatically.
- L1: focused checks. L2: component/flow checks plus visual review when appearance changes. L3: full declared page/flow coverage. Do not run irrelevant suites repeatedly after every edit.
- Build/lint/test success is one kind of evidence. Browser assertions, screenshots and visual observations cover different conditions. Report missing tools honestly and attempt reasonable local setup within task scope.
- Keep generated assets local and referenced, optimize dimensions/format/size for their display use, and check loading/cropping. Avoid large raw images for tiny decoration.
- Fix source and re-run affected checks. Editing an audit document or changing evidence labels does not repair a page.
