# Components

- Discover the current component system first. Reuse suitable accessible primitives and project patterns. Install dependencies only when they serve the task; avoid stacking several UI kits.
- Prefer StyleKit resources for new pages and full redesigns. Retrieve suitable component recipes, dynamic components and template source first. Actual StyleKit resources may supply primary UI. Record concrete unavailability or incompatibility before selecting a supplemental library from the original list.
- Obtain StyleKit resources through actual official queries and inspect source, version, dependencies and license. Use Context7 to verify project libraries and runtime APIs. If unavailable, consult official documentation and record the actual limitation.
- Shadcn and Material UI require substantial visual customization within applicable visual work. Default controls with recolored backgrounds are insufficient evidence of such customization.
- Functional icons use a consistent SVG/icon system, never Emoji. Keep labels, forms and essential operations as real accessible elements.
- Inspect actual computed styles and loaded runtime code, including library internals, portals, shadow roots or iframe boundaries when relevant. If a tool cannot inspect a boundary, mark that portion unverified.
- Verify focus, hover/pressed/disabled/error/loading states applicable to the change. Existing components may be preserved when a local task does not request their redesign.

## Required execution record
For L3 production and applicable new component work, fill task.component_libraries before implementation, then update actual execution evidence. decision=none is not permitted for required new visual UI adoption. It remains scoped to local/unrelated maintenance where library adoption is not applicable. Existing HTML, no suitable library, avoiding a framework, and already handwritten are not exemptions for new UI. Use a compatible listed library rather than defaulting to a rewrite or a helper. If none is compatible, describe the specific conflict; do not silently deliver handwritten UI as compliant.

For each used source, record actual name, version/revision, docs_provider, docs_evidence, usage, customization and render checks. Package imports must match actual usage. StyleKit vendored resources instead may qualify through the source acquisition and current file bindings described below. Official fallback for other libraries additionally requires the actual Context7 limitation. Inspect real tool history, runtime and screenshots when judging adoption.

For Shadcn/Material UI compare the resulting components with the default across relevant states. Recoloring a default rounded button is insufficient. Record concrete differences and screenshot regions under component_customization and relevant rule IDs. Evaluate fit with the selected direction, icon consistency, responsive behavior and keyboard operation. Do not install every candidate library or force a framework-incompatible library merely to populate a record. Records and usage files join evidence fingerprints.

## Primary UI adoption evidence
Required items use role=primary_ui and the canonical name (StyleKit, Magic UI, Aceternity UI, DaisyUI, Brutalist UI, Glass UI, Radix UI or Mantine). Helper items use role=helper and cannot satisfy this requirement, even when imported and working. For package distributions, module identity must match the chosen library; registering Mantine while importing a11y-dialog fails. For copied/registry components use distribution=vendored and source_evidence recording the actual source acquisition, revision and copied implementation. Local copied components are valid adoption when their origin and actual use are demonstrated; installation is not mandatory for registry-based libraries. Source records do not authenticate themselves.

Each primary library declares render_checks entries with page, width, state, selector, component and implementation. The implementation belongs to that library's usage paths. Fixed browser execution must actually execute expect_visible for the same scope and selector. Choose main form/navigation/content components; a decorative demo widget or an unrelated visible selector is not meaningful adoption. Match imported/copied code, actual runtime, component roles, states and customization in review. A visible selector does not independently prove it was built from that library, so do not claim this check authenticates provenance or visual quality.

For a full page, using only a listed library's dialog/tooltip/icon is also insufficient. The checker flags all-overlay/icon component declarations as incomplete coverage; names are a heuristic, not proof of component behavior. A scoped L2 dialog task can legitimately use that library's Dialog alone. Do not add unrelated widgets to a local patch to satisfy a page-wide coverage rule.


The usage scanner recognizes CSS @plugin declarations and stylesheet href entries as well as JS imports. In particular, DaisyUI's official install uses @plugin "daisyui" in CSS: https://daisyui.com/docs/install/ . This prevents rejecting real CSS-library adoption; it does not replace Context7 verification for an actual project or certify that the components are customized.


## StyleKit-first records

L3 component_libraries.stylekit_priority contains decision=used or fallback, reason and search_evidence pointing to the actual resource-query record. A StyleKit primary item uses name=StyleKit, role=primary_ui, distribution=vendored, version=actual asset revision/hash, docs_provider=official and actual docs_evidence, usage, customization, source_evidence and render_checks. Verify runtime dependencies through Context7.

source_evidence is a JSON acquisition record with source_url, asset_id, the original fetched response, and files entries with path and sha256 for the actual adapted implementation. Copied resources may use imports=[] when those files are directly rendered. The checker requires current file bindings and actual render assertions. Metadata-only results need a documented fallback. A record alone cannot authenticate a tool call, so inspect actual query history and source content.

StyleKit files bindings 必须覆盖全部 usage 与实际 primary render implementation，修改任一文件后更新绑定并重验。
