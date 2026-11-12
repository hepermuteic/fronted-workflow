---
name: frontend-workflow
description: Use only when the user explicitly invokes frontend-workflow for frontend design, implementation or verification. Preserves the user's design rules, StyleKit direction, real browser evidence and independent Critic review across frameworks.
---

# 前端设计与交付

版本 7.0.0。负责风格选型、详细设计、实现、真实验证和交付。仅明确调用时启用，覆盖当前任务及明确续作。普通前端请求按全局入口执行，Skill 维护按维护范围执行。

## 开始与范围

新任务完整读取 [设计规则](references/frontend-design-rules.md)、项目需求和已有架构。同一上下文复用哈希未变的已读材料，按阶段读取相关参考。L1 处理局部文字与样式，L2 处理组件或局部页面，L3 处理新页面与整页改版，所有范围内要求继续适用。既有选型和已有授权按本次需求延续。

首次安装运行 `python scripts/install.py`，安装与环境问题查 [安装说明](references/installation.md)。维护记录见 [更新日志](CHANGELOG.md)。

## 执行步骤

1. **选方向**。先按场景查询 StyleKit 目录和候选 brief，再用内置 Image 当前可用能力生成 A/B/C/D 四张不同视觉语言的参考，直接展示并等待用户选择。图注写实际风格名称和 slug。按 [风格发现](references/style-discovery.md) 与 [StyleKit 接入](references/stylekit-runtime.md) 执行。已有选型的续作沿用该方向。
2. **写设计**。固定选定的 StyleKit slug，获取页面语言的完整 design.md 和 Implementation Contract，原样纳入项目 design.md，追加本次适配。优先使用实际 StyleKit 资源，补充库核对 Context7。将构图、材质色彩、字体、必要文案、成套素材、动态组件和验收条件一次确定。字段见 [设计文档](references/design-document.md)，细节按需查 [布局](references/layout.md)、[字体](references/typography.md)、[组件](references/components.md)、[动效](references/motion-routing.md)、[素材](references/assets.md) 与 [文案](references/copy.md)。
3. **准备并制作**。用 `scripts/verify.py init` 建立当前任务，返回的 discovery 同时提供项目命令与技术栈。填写适用范围后，用 `scripts/scaffold.py --root <项目>` 生成缺少的计划、浏览器用例和复核模板。按 [编码前检查](references/preflight.md) 通过计划检查后实施。design.md 统一维护设计说明，style_summary 与 asset_plan 可引用它的对应内容。先做好主要区域，再按 [开发](references/development.md) 扩展到本次范围。
4. **成批验证与改进**。一轮是完成一批相互关联的实际修改。先统一处理本轮已知问题，再对当前版本执行检查、操作、截图和 Critic。可用 `scripts/cycle.py --root <项目>` 按已填写的运行计划顺序执行命令、浏览器和评审，命令失败时先修复。相同输入与完整有效凭证的成功命令直接复用。浏览器用例合并在一次进程中，覆盖实际页面、状态和视口。按 [验收](references/acceptance.md) 与 [运行绑定](references/runtime-binding.md) 执行。
5. **独立复核并交付**。按 [Critic](references/critic.md) 在全新上下文仅提交当前截图与固定提示，模型固定 gpt-6.1-terra / high。主 agent 优先处理结构、构图与最大差距，再改细节；分数低于 9 时继续实际修正。相同版本的有效评分直接复用，最终收尾使用这一轮评分。L2/L3 同时完成 [独立合规复查](references/independent-review.md)。按 [交付复核](references/delivery-review.md) 合并已发现的问题与实际修正，运行一次 `finalize`，再按 [受保护批准](references/visual-approval.md) 完成适用批准，签名登记后运行 `check`。

## 效率与质量约束

- 同一份真实材料支持多个条件时集中保存，各条保留具体条件、位置和实际观察。脚手架只生成未完成结构，检查结果由实际执行产生。
- 实际修改、检查结果或新发现使相关材料失效时，重做受影响步骤；同版本材料保持有效时直接继续下一步。修复一批问题后再启动下一轮外部评审。
- 参考阶段保持四图快速选型。正式阶段集中完成真实组件、素材和动态反馈，按实际缺口补齐。
- Critic 的 9 分门槛由主流程持有，固定评审提示保持中立。低分复用后继续修改，原始分数和最新轮次完整保留。
- 原设计禁令、逐项落实、真实测试、独立复查和受保护批准共同决定交付。未做、失败和受阻按事实记录，具体机制见 [效率说明](references/efficiency.md)。

## 输出标准

选型阶段输出四张风格参考与图注。正式阶段输出完整 design.md、可运行实现、所用素材与组件依据、逐项实际结果及当前截图。交付简述完成范围、测试、Critic 分数与剩余问题，附可核对文件，最后给出一个 `最终状态：PASS / FAIL / BLOCKED`。总体 PASS 满足全部适用检查和有效批准。

复用文件位于 assets/templates，自动化入口位于 scripts，完整执行器随包提供。发布维护查 [发布检查](references/release.md)。
