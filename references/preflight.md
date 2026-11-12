# 编码前检查

此检查验证计划是否齐备，不批准 UI，也不证明工具来源。它只用于明确调用本 Skill 后的 L2/L3 视觉实现；维护规则、只读审计、参考选型和局部文字任务不强制走新页面流程。

确认场景及选定方向后，先生成项目根目录 design.md，再运行 init 并填写结构化计划。文档格式见 design-document.md。**运行 `preflight` 得到阶段 PASS 后开始编码。** 缺少真实资料就补资料；不要把未做的内容写成已做。这个命令不生成素材、不安装组件、不联网、不授予 Hook 信任。

```powershell
python '<skill>/scripts/verify.py' preflight --root '<项目绝对路径>'
```

`task.design_plan` 格式如下。字段值必须来自当前任务；下例是结构说明，不是可直接交付的设计。

```json
{
  "selected_style": "A",
  "scene": "当前产品场景与主要任务",
  "style_direction": "选定视觉语言及适配依据",
  "tokens": {"--color-ink": "实际自定义色值"},
  "layout_regions": [
    {"selector": "main", "decision": "写明主要区域的宽度、位置和内容分配"}
  ],
  "typography": "字体、字重和字号层级的具体选择",
  "material": "背景纹理或渐变如何实现",
  "copy": "文案必要性与事实来源",
  "motion": "实际使用的非线性缓动；没有动效则说明",
  "assets": [
    {"role": "object_cutout", "purpose": "写明产品场景", "placement": "实际页面区域"}
  ]
}
```

- L2 只计划本次受影响区域。`layout_regions` 不需要虚构多个页面。原组件库条款适用时仍须选择主 UI 库。
- L3 须有真实选定记录、风格摘要、素材计划、落实清单和项目要求；新方向先完成四套风格参考。用户自行给定的新方向可记 `user_custom`，原始用户指令仍须留证。
- L3 不能把原规则核心设计章节整批标为“范围外”。可选着色器、Tripo 3D 保留采用/不采用和理由，不强制购买或生成无关模型。
- 主 UI 库要在编码前选定：真实版本、Context7 查询依据（受限时为官方文档和限制）、计划 import、主要组件及实际定制方法。只用弹窗、图标工具不够。`usage` 和 `render_checks.implementation` 可以是即将创建的文件；交付检查时必须实际存在并使用。
- 素材计划不能只列背景。正式阶段至少一项内置 Image 生成的非背景内容素材。四套风格参考不充数；本命令的阶段 PASS 不证明已经生成。
- 不额外要求用户批准每个常规步骤。用户尚未选风格、具体要求冲突或缺关键输入时才处理该依赖；不能自行制造用户同意。

凭证绑定本任务、计划、规则版本。改方向、范围、组件选型或验收条件后重跑，并复查受影响实现。不要为过门禁降低验收条件。该检查是工作流关口；本地工具并不禁止所有编辑器或 Shell 写文件。

正式 L2/L3 视觉制作将 task.design_document 设为 design.md。L3 的 task.design_plan.dynamic_components 覆盖每个声明页面，具体字段与执行断言见 design-document.md。文档修改使旧 preflight 凭证失效。


## 4.0 选型与引擎记录

L3 正式任务填写 task.style_discovery，内容格式见 stylekit-runtime.md。design_plan.motion_plan 包含 engine、reason、docs_evidence，以及 pointer 的 decision、reason、touch_fallback、keyboard_fallback、reduced_motion、cleanup。文档证据与选型文件进入指纹。选型阶段保持轻量，正式编码前补全这些工程记录。

## 4.3 区域、素材与按钮

L3 填写 design-document.md 中的 visual_surfaces、asset_coverage、button_feedback。素材覆盖表覆盖声明页面；generate 项有实际落点，omit 项说明为何该处不需要图像。数量按场景确定。没有按钮的界面填写 button_feedback_reason，不虚构控件。L1/L2 不为这些新字段扩大任务范围。

动态组件 verification.steps 使用 remember_state → 输入动作 → expect_state_changed；支持 text、attribute、value、checked、disabled、visible、url。name 关联基线与结果，attribute 指定实际 aria/data 或状态属性。可写 value 限定真实初始/最终值。按钮视觉 verification.steps 使用 remember_style → 实际输入 → expect_style_changed，基线 selector 指向该按钮。颜色、阴影、变形等选实际效果对应属性，操作结果另作状态检查。不能用 click → expect_visible 同一个按钮冒充变化。

这些字段检查设计决定和执行覆盖；机器不因此认证色彩还原、素材复杂度或动效品质。最终逐区视觉对照仍适用。

## 4.4 逐项计划与结果

L3 编码前填写 task.checklist_plan 的 JSON 计划，格式见 acceptance.md 的 4.4 章节。覆盖 applicable 原规则和项目要求，写具体决定、实现、条件和证据检查对应关系。task.implementation_checklist 指向独立 Markdown 结果路径，首次 preflight 时该结果文件可尚未生成。相关检查和改进复核完成后，按 delivery-review.md 用 finalize 合并清单同步与最终交付检查。需要提前查看清单时可单独使用 checklist-sync。

四种新方向的 style-discovery.options 记录 style_name 和 style_slug，图注展示实际风格名称与来源标识。已有选型沿用真实记录。
