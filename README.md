# frontend-workflow

版本 7.0.0。用于前端风格选型、详细设计、实现、真实验证与独立 Critic 复核，仅在用户明确调用 frontend-workflow 时启用。

## 安装

需要 Python 3.10 或更新版本。本版已在 Windows 环境验证。

克隆仓库后运行以下命令。

```sh
git clone https://github.com/hepermuteic/fronted-workflow.git
cd fronted-workflow
python scripts/install.py
```

也可下载 [ZIP 安装包](dist/frontend-workflow.zip)，解压后运行以下命令。

```sh
python frontend-workflow/scripts/install.py
```

安装依赖与 Playwright 可添加 `--setup-tools`。默认安装位置为 `~/.agents/skills/frontend-workflow`，安装器同时写入用户级指引、Critic 配置和 Hook 定义，并备份已有修改。

## 使用

在新会话中明确说“使用 frontend-workflow，按我的原规则制作这个页面”。

- [Skill 入口](SKILL.md)
- [安装与迁移](references/installation.md)
- [设计规则](references/frontend-design-rules.md)
- [更新日志](CHANGELOG.md)
- [发布检查](references/release.md)

ZIP SHA-256 为 `281cf5b23dcfc8a209c1026e5080d8b2aaaaa07d38086e8c156f32e14a5144b3`。
