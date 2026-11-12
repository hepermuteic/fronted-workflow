# 安装与迁移

文件夹名称为 frontend-workflow。包中包含 SKILL.md、agents、references、scripts 和 assets。references/frontend-design-rules.md 是完整设计要求的唯一维护来源，scripts/engine 保存全部执行器，用户目录保存运行状态和凭证。

使用 Python 3.10 或更新版本运行安装器。

```sh
python frontend-workflow/scripts/install.py
```

默认安装到当前用户的 ~/.agents/skills/frontend-workflow，写入 Critic 自定义代理、全局指引和 Hook 定义。安装器保留无关配置，修改前备份已有文件；相同版本重复安装保持已有内容。旧 ~/.codex/frontend-policy 命令转到包内执行器，旧规则路径保留读取新来源的入口。

需要安装 Python 依赖和 Playwright 时使用以下命令。Node.js 与 npm 需可执行。

```sh
python frontend-workflow/scripts/install.py --setup-tools
```

Python 依赖定义在 scripts/requirements.txt。浏览器优先查项目依赖、用户 tooling，再查宿主随附运行时。执行安装检查。

```sh
python ~/.agents/skills/frontend-workflow/scripts/verify.py doctor
```

调用时说“使用 frontend-workflow，按我的规则制作这个页面”。已有风格时补充选定方向和本次修改。第一次载入用户级 Skill 与代理可新开会话。

## 集成状态

Hook 定义安装后，宿主按正常机制审核信任，实际生命周期仍须实测。受保护视觉批准按 visual-approval.md 配置本地独立审批身份与受保护存储，正式视觉交付使用真实签名。安装器输出 INSTALLED 说明文件集成已完成，doctor 的结果说明当前检查范围。

本版以 Windows 环境验证运行、浏览器和安装，受保护审批继续使用 Windows 权限隔离机制。已有项目保留资料与选型，迁移后重读规则并刷新失效的计划和证据，原始旧结果继续保留。

## 维护与分发

维护已安装文件夹中的规则、参考、脚本和模板。分发只包含 SKILL.md、CHANGELOG.md、agents、references、scripts、assets，排除业务 outputs、凭证、密钥、缓存和机器依赖。scripts/package_skill.py 可生成干净文件夹和同内容 ZIP。
