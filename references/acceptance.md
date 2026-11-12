# Task-scoped acceptance

This workflow is explicit-only. Its dedicated task/evidence files, reminders and Stop checks apply after the user explicitly invokes frontend-workflow for this task. Ordinary frontend prompts or UI file edits do not enable it. The original design rules remain independently applicable. Opting out stops these workflow-specific checks; no missing workflow record should block an uninvoked task.

## Status semantics
- PASS: required executable checks in the declared scope passed, with valid runner receipts where required, and no unresolved acceptance requirement. Nonvisual/lightweight tasks can qualify. Model visual self-review never authorizes overall PASS.
- FAIL: a known violation, failed command, failed browser assertion or failed visual criterion remains.
- BLOCKED: required tools, evidence, scope or observations are missing/unverified. It is not a softer PASS.
- References may finish awaiting user selection, with stage-scoped automated results; this does not certify final UI. No script can decide beauty, validate real devices it did not operate or prove that an agent did not fabricate artifacts.
- Formal visual tasks report automated_status separately. Final approval follows visual-approval.md and requires a valid reviewer signature pinned by the protected trust store. Missing isolation, keys or receipt leaves BLOCKED. Reference-only handoff awaits selection and needs no delivery verdict or task plan when no product code has been edited.

## Start from the project
Reuse the current task's discovery results when project configuration is unchanged. If results are missing or configuration changed, run `scripts/verify.py discover --root <project>` and inspect actual scripts and existing components. React, Vue and static HTML use the same evidence model but different commands. Never install or launch the same toolchain blindly in every repository.

Initialize before edits, for example:
```powershell
python '<skill>/scripts/verify.py' init --root '<project>' --level L2 --summary 'Change the affected component' --files src/Component.vue --pages settings --widths 390 1280 --states default error --interactive
```
Use actual paths and scope. L1 does not require image generation or full visual checks unless the change needs them. `--visual`/`--no-visual` selects applicable verification; L2 nonvisual work needs `visual_reason` in the plan, and L3 interface work requires visual verification. `strict` is the default; `project` and `expressive` are compatibility aliases with identical mandatory checks. `--phase reference` declares a reference-selection task. `--replace` starts a new task and archives the previous task plan.

Plan: `work/frontend-policy/task.json`. Evidence: `work/frontend-policy/evidence/<task_id>/`. Result: `work/frontend-policy/result.json`. Do not duplicate global standards in project instructions.

## Run project checks
The `checks` array contains task-applicable IDs/types. Keep required source/browser/review checks and available project checks. Add relevant checks before executing them; optional checks need a concrete scope reason.
```powershell
python '<skill>/scripts/verify.py' run --root '<project>' --check-id project-check -- node.exe '<actual-test-script>'
```
Arguments after `--` are an explicit argument vector, not an inferred shell string. For a shell/batch command, supply the intended shell explicitly or use the package manager's executable entry point. The runner records actual exit code, output log and file hashes; Hook execution never launches these commands automatically. Commands time out after five minutes; use an appropriate existing test command or run longer work explicitly and record its actual outcome through the project's tool.

## Real-browser evidence
1. Declare the affected `page`, `width`, `state` combinations in task.scope. Include relevant validation, overlays, feedback, empty/error/loading states; do not invent irrelevant ones or omit known ones to pass. Component-only work may capture its actual enclosing region using ROOT_SELECTOR in capture.js.
2. Launch the project using discovered commands. Exercise each required state with real assertions. A screenshot or a focus call alone does not prove an interaction; record the expected/actual flow outcome and command log.
3. Use fixed browser-run to invoke the collector and capture PNGs. Do not edit global capture.js to scope one task: set root_selector on the relevant task.scope entries when only an affected component needs inspection.
4. The fixed process captures loaded script/stylesheet responses and hashes the actual files it observed. These bytes plus local inputs are bound to execution receipts. A local source hash does not by itself prove that a remote server deployed that source; inspect the target URL/build and runtime together.
5. Capture applicable states, not only the initial screen. The collector includes open shadow roots, rendered CSS-generated text, computed modern color conversions, relevant animation segments and layout geometry. Iframe/closed-shadow boundaries are unverified until separately inspected; resizing desktop Chromium does not test a real mobile keyboard.
6. Imported capture JSONs may be inspected for diagnostics, but do not qualify as executed browser checks. To obtain execution evidence, create a declarative spec and run the fixed browser process:
```powershell
python '<skill>/scripts/verify.py' browser-run --root '<project>' --spec work/browser-spec.json
```
Spec shape: `{"cases":[{"page":"main","width":390,"state":"default","url":"http://127.0.0.1:3000/","steps":[{"action":"expect_visible","selector":"h1"}]}]}`. Cases must match planned scope. Supported actions: click, fill (value), press (key), check, expect_visible, expect_hidden, expect_text (value), expect_url (value), expect_css_number, expect_area_ratio and expect_in_viewport. Every state needs at least one actual assertion. No arbitrary JavaScript or submitted PASS field is accepted. The fixed runner navigates, acts, asserts, captures DOM/screenshots and runtime responses itself; source changes during the run abort it.
It writes captures and process evidence, then issues a receipt in the user-level receipt registry. Manually editing a project evidence JSON cannot substitute for this execution. Changed source, artifacts, task contract or policy invalidates the receipt.
The checker reconstructs complete semantic units from rendered DOM, including checkbox labels and adjacent agreement buttons. Card headings, descriptions and metadata remain separate semantic units. Use a whole-sentence data-copy-unit container when structure is ambiguous. Review necessity, repetition, tone and factual accuracy; there is no fixed character limit.

## Visual review
Write a JSON array of actual observations, each with `criterion`, concrete `location`, `observed`, `status` (PASS/FAIL/BLOCKED) and local `evidence` paths. Cover each ID in task.review_criteria and add task-specific criteria before coding. Minimum criteria follow level and interactive scope; they cannot simply be deleted to pass. Review applicable typography/contrast, composition/density, component states, assets/crops/weight, responsiveness and selected direction. Shared files are allowed; generic copied conclusions are insufficient.
Register it using `review --observations <json-path>` (default check ID visual). This is explicitly an agent review attestation, not independent machine certification. Filling it with PASS cannot unlock overall PASS. Unverified criteria stay BLOCKED. Never change a failed criterion to PASS merely to allow delivery.

For every applicable rule:<id> observation also supply implementation (actual local source paths) and condition (the specific acceptance condition). Reusing a screenshot is allowed; copying the same location/observed sentence into different criteria is not. Actual source files join artifact hashes. Review user project constraints as well as the global rules: record where each comes from, how it is implemented and what was actually checked. In particular, typography-led hierarchy, illustration prominence, small auxiliary type or initial-viewport density must follow the user's selected direction and project brief; do not turn one project's values into universal defaults.

## Reference and asset records
Reference selection is lightweight: display the four actual A/B/C/D images directly in conversation, add brief theme labels and await user choice. No gallery, build, browser run, formal review, independent review or per-clause dossier is required at this stage. Do not create a task plan solely to show references. If a reference task already exists, its default check only validates four distinct image artifacts; it does not certify final UI or prove style quality/tool provenance. task.reference_gallery is optional legacy metadata, never a requirement. Formal implementation, evidence and acceptance begin after selection; those requirements remain unchanged.
For L3 production, task.assets registers actual files with `origin: builtin_image`, a non-background `role`, concrete `purpose`, rendered `url`, and local `generation_evidence`. The browser must demonstrate that the asset loaded and appears. File presence is insufficient; original logos, textures and backgrounds do not satisfy the mandatory content-asset requirement. See assets.md for planning, transparent cutouts and visual integration. Provenance is not authenticated by a JSON field and must be supported by actual tool use.

## Delivery guard

Visual implementation also requires the screenshot-only Critic workflow in critic.md. Each iteration uses the fixed neutral prompt, gpt-6.1-terra with high reasoning and a fresh context. The parent workflow holds the score threshold. Current score below nine is FAIL and missing, stale or unexecuted review is BLOCKED. Existing implementation checks and protected approval remain jointly required.

Read delivery-review.md for the final improvement pass. Every delivery reviews the current requirements and implementation. L2/L3 implementation records concrete observations, resolved improvements and recheck evidence, then uses finalize to sync the checklist, run one full validation, seal the review and check protected approval. Its current receipt and fingerprint join the delivery gate and visual approval bundle. After an implementation, plan or evidence change, repeat the affected checks and final review.
Repair failures from the computed `finalize` result. Use standalone `check` after registering a protected approval receipt or for step-by-step diagnostics. A stale/missing record is BLOCKED; failed checks are FAIL. `run` launches the actual process and records exit code/logs; browser-run launches the fixed browser process. Their qualifying records require a registry receipt bound to the actual record and task contract. A self-written PASS JSON, imported DOM and a set of screenshots alone cannot qualify. Scope completeness and meaningful test design still require judgment; running a no-op is not meaningful product coverage.
Finish with actual work, standards, checks/commands, visual findings, limitations and one computed `最终状态：PASS|FAIL|BLOCKED`. State the scope of a PASS. Global Stop compares the declaration to the result, requests repair/correction for mismatches, and stops after two unsuccessful continuations with a warning. This bounds token use; it is not an absolute guarantee that a host will hide every earlier incorrect sentence.

## Maintenance
This skill and the canonical verifier are user-level resources. Hook trust/activation is checked separately in the application's Hooks UI. User approval of a design does not trust a new executable Hook definition. Policy updates require review when the host requests it. No model calls are needed to validate local files and Hook command protocols.

The receipt registry is outside project evidence but shares the same OS user. It is not a cryptographic/permission boundary against an agent that deliberately rewrites the verifier or registry. To defend against same-user malicious forgery, use a separately administered read-only runner, protected CI and an independent approval identity. No such external service is claimed installed here.

## Four priority areas
For L3 production record task.component_libraries and task.space_effects. Library requirements also activate for scoped tasks declaring the relevant original library clauses applicable, or whenever library records are supplied. Read components.md for actual version/docs/import/customization fields. Read copy.md for copy necessity, complete meaning and tone/factual review; visual minimum criteria include copy_tone_and_facts, component_customization and layout_regions for L2/L3.

Read assets.md for Image generation, content assets and optional shader/model decisions. Generated content-asset records need purpose, generation_evidence, usage paths and URL. Fixed browser execution collects actual image/model response hashes; generated content files must match loaded bytes. Identical registered reference images cannot satisfy production assets. L2 registered generated assets are checked too, without forcing unrelated content generation onto local changes. Records do not authenticate a tool call. Actual model/shader adoption additionally requires the declared fixed-runner visible-render assertion; neither visible canvas nor loaded bytes establish correct 3D rendering on their own.

Component documentation and usage files, image generation/usage files, spatial effect files and their generation records join fingerprints; inline plans join the execution contract. Layout snapshots measure regions and child bounds at actual viewports. Measurements do not automatically certify asymmetry, composition or absence of the Hero-plus-three-cards template. Known failures remain FAIL; missing records/evidence remain BLOCKED; subjective visual acceptance still cannot be self-awarded.

## Binding to the original document
The sole design authority is `references/frontend-design-rules.md`. Read it in full. `catalog` checks every source bullet against `original-rule-map.json`; missing/stale routes block verification. A route is not proof that its full text is machine checked. The original file participates in policy_hash and task.original_rules_sha256, so changes invalidate old evidence. Hash binding cannot prove the agent read it.

Before coding, preserve the existing planning material and cover applicable source clauses and project requirements with their IDs, concrete decisions, implementation paths, verification methods and expected conditions. L3 uses the frozen checklist_plan JSON described in section 4.4 and generates implementation_checklist Markdown after actual checks. Run catalog for source IDs and resolve every rule_application entry as applicable/out_of_scope/conditional with a specific reason. Optional source clauses may be conditional. A mandatory conflict requires the user's explicit decision.

For each applicable `visual_review` route, add a `rule:<id>` observation against actual screenshot regions. Even L1 must enable browser/review scope when it claims an applicable visual requirement; a text-only source scan cannot certify the visual result. Tool-provenance and workflow routes explicitly remain dependent on real history and review, not authenticated by user-written fields. Out-of-scope reasons still require judgment and cannot be independently proven by this local checker.

L3 production registers actual selection_evidence, style_summary and asset_plan files, plus checklist_plan and its implementation_checklist output path. The frozen inputs join source fingerprints. The generated checklist is refreshed from actual evidence and bound to the final approval signature. Its file may be absent before initial preflight. Legacy tasks without checklist_plan retain full Markdown source binding and receive the migration instruction. Preserve the actual user choice and used non-background assets, then complete independent review and the protected procedure in visual-approval.md.

## Before implementation and release
Read preflight.md for L2/L3 visual implementation. preflight PASS is a planning-stage result, never a product acceptance result. The final checker requires its current task/plan/policy receipt. It also binds baseline snapshots and asset/reference metadata, so changing a file role or editing a baseline cannot preserve an old execution receipt. Project commands that modify tracked inputs cannot certify the starting revision; rerun against the resulting revision.

Whole-sentence checks include visible aria-hidden copy, inline splits and CSS-generated text. Hidden DOM is excluded by actual browser collection. Modern CSS colors are converted by the browser before hue checks. Clear equal-width grid/flex rows are flagged as candidates; whole-page centering and Hero-plus-three-card composition still need actual review. The material check finds candidate page-scale gradients/textures; absence is unverified, not proof of a good or bad aesthetic. Raster image colors and inaccessible rendering boundaries remain review scope.

There must be exactly one final status declaration. A matching BLOCKED/FAIL line does not excuse contradictory claims that everything passed. An unreadable active task blocks unsupported PASS instead of falling through a nonblocking Hook error. Honest blockers can end the turn. No Hook hides every prior sentence or prevents every possible filesystem edit.


Read runtime-binding.md before qualifying browser execution. Actual document and same-origin runtime bytes must match the declared static sources or a real source-bound build and its outputs. A correct assertion against an old page cannot qualify current code. Compiled applications declare deployment.mode=build, deployment.check_id and outputs on that command check. Unsupported dynamic server transformations remain unverified rather than accepting arbitrary page bytes as current sources.

Initialization snapshots are registered outside project evidence. Editing a baseline, removing initially declared source files or lowering the initialized task level cannot hide new violations. Scope can expand to stricter validation. This registry remains writable by the same OS user and is not a hostile-tampering boundary.


## 4.0 指针与风格验证

L3 preflight 要求真实来源的风格选型记录和动效引擎/鼠标交互决定。固定浏览器支持 hover、move_pointer（x_ratio/y_ratio 在 0..1）、remember_style（name/property）与 expect_style_changed/expect_style_unchanged（name）。用例设置 reduced_motion=reduce 或 no-preference。基线与断言在同一用例内，按实际操作检查 transform/opacity/filter/boxShadow 的变化。触屏和键盘回退需按产品行为单独断言。

## 4.3 材质、素材与按钮验证

reference_fidelity 观察增加 surface_comparisons 数组，对 visual_surfaces 每个 selector 记录 expected、observed、deviation、decision。偏差不存在时也写具体比较结果；有偏差则修复或说明必要适配。观察的 evidence 仍需包含本次真实截图，reference_file 对应登记来源。机器检查区域覆盖，不判断这些描述是否正确，独立复查和受保护批准仍须查看实际材料。

asset_coverage 中 generate 项用相同 id、role 关联 task.assets，并填写 render_check 的 page、width、state、selector。selector 指向实际 img；固定采集器核对该位置的加载 URL、图像字节和有效可见性。透明、隐藏、完全裁剪或只登记未显示的图片不能充数。成套丰富度、细节、裁切和实际尺寸仍按 assets 观察判断，不由图片数量决定。

动态验证记录 state_changes，按钮视觉记录 style_changes。两者包含真实 before、after、trigger_steps 及步骤索引；序列写在计划中、实际调用了 click、截图里有按钮，都不足以代替测量。按钮反馈按所选样式可测 transform、opacity、filter、boxShadow、backgroundColor、color、borderColor、borderTopColor、outlineColor、outlineWidth。实际输入必须在基线与变化断言之间。expect_text、expect_url、expect_state_changed、expect_style_changed 支持 timeout_ms（1..15000，默认5000），等待异步结果而非提前伪造成功。

页面材质检测排除恒色/全透明渐变、零透明度层。组件区域检查不强迫每个按钮自己拥有页面背景。通过候选检查不能证明纹理强度、配色比例或风格已还原。

## 4.4 逐项结果同步

5.1 使用 finalize 合并清单同步、完整验证、最终复核绑定与批准检查，具体记录格式见 delivery-review.md。适用的受保护批准签发后执行 check 核验签名与当前版本。正文按 typography.md 检查声明与实际字形，微软雅黑的直接使用、别名和实际回退都进入检查。

L3 正式制作将冻结的逐项计划登记为 task.checklist_plan，例如 work/frontend-policy/checklist-plan.json，Markdown 结果登记为 task.implementation_checklist。L2 使用逐项自动结果时采用同一格式。计划覆盖所有 applicable 原规则与项目要求，每项包含具体设计决定、实现位置、通过条件和对应检查。

```json
{
  "schema": 1,
  "entries": [{
    "id": "project:readable-copy",
    "decision": "正文采用项目确定的可读字号，并合并重复提示",
    "implementation": ["src/Practice.tsx"],
    "condition": "在项目声明的窄屏尺寸读清完整说明",
    "verification": {
      "check_id": "visual",
      "criterion": "project:readable-copy"
    }
  }]
}
```

原规则条目用 rule:<catalog id>，项目条目用 project:<project requirement id>。review 精确对应同名 criterion，记录实际区域、观察、状态和证据。browser 项填写 page、width、state、assertion，断言必须与实际执行记录匹配。command 项绑定冻结的命令检查与日志。workflow 和工具来源条款由同名观察及实际依据核对。现有素材、浏览器与工具来源检查仍执行各自的完整要求。

完成相关检查、观察和改进复核后合并交付检查。

```powershell
python '<skill>/scripts/verify.py' finalize --root '<项目>' --observations work/delivery-reflection.json
```

清单同步从当前执行凭证、具体断言与观察推导 VERIFIED、FAIL、BLOCKED，保留实现、条件、实际结果与证据。同批次复用文件、源码指纹与执行凭证的读取，结束前重新核对真实内容、路径与凭证。每项具体断言、观察、设备方法仍分别检查；任何内容变化使本批次受阻，跨次调用不沿用缓存。初次执行会将目标中已有的用户 Markdown 保存在同目录 .before-sync.md。最终 check 重算并核对生成文件，缺项、通用观察、未测、失败、陈旧证据及手改结果逐项报告。review 行显示 Review attestation，来源仍由实际材料和受保护审批审核。

冻结计划参与 preflight、源码指纹及执行凭证。生成结果可在检查后刷新，全文进入视觉审批材料与签名。调整条件、实现范围或计划后重跑受影响检查。旧任务保留原 Markdown 的全文指纹，迁移时从原文提取具体计划，保留原资料并刷新证据。已有风格继续按真实选型执行。

构图对照在 layout_regions 和 reference_fidelity 中记录关键组合及空间关系，正文阅读记录在 readability 中。采用参考中的宽内容与窄操作入口、嵌入进度或曲面时，对照实际组件和目标尺寸。字号阈值按本次设计确定，使用 expect_css_number 等实际断言检查，连同真实文字、行高、对比度和放大表现复核。

在项目验收计划明确真实触屏、完整焦点巡检、屏幕阅读器各自的适用范围。需要实测的项目写入 project_requirements 与清单，对应 review 观察分别声明 method 为 real_touch、focus_audit、screen_reader，verification.method 与观察匹配。观察的 verification_details 填 environment、tool、coverage、steps 数组、expected、actual，证据记录实际会话日志或操作结果。environment 写设备/系统/浏览器，tool 写工具及版本，coverage 写页面和状态范围，steps 写完整操作路线。缺少工具、设备或过程证据保留 BLOCKED。桌面触摸模拟、自动扫描及部分 Tab 步骤记录各自实际覆盖范围。
