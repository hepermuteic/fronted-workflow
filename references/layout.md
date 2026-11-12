# Layout and responsive behavior

- Start with user goals and information priority. Place the next useful action and enough real content in the initial viewport; avoid large decorative areas that push useful material away.
- For applicable UI work, identify the substantive asymmetry: unequal content allocation, offset regions, variable density or deliberate negative space. Moving an illustration slightly or widening one navigation item is insufficient by itself.
- The original rules prohibit equal-width columns and fully centered page compositions, including navigation/toolbars unless the user explicitly grants an exception. Retain usable form order and semantic navigation; existing component behavior is not redesigned during unrelated L1/L2 work.
- Choose viewports from the project's supported devices, not a universal mandatory list. Check narrow and wide limits and relevant short-screen/keyboard conditions. A no-overflow script is not a visual review.
- Inspect actual typography, line breaks, clipping, alignment, scroll regions, touch targets and fixed elements in each required state. Do not let motion, images or overlays obscure primary actions.
- Record specific selectors/regions and observed results. A shared screenshot can support multiple findings, but each finding needs its own condition and conclusion.

## Layout evidence
Use layout_regions and applicable rule IDs to describe at least the relevant major regions: content allocation, widths/heights/positions, hierarchy and reading order. Fixed browser snapshots include layout_regions with bounding boxes and grid columns/child bounds; use these as measurements, not a beauty score. Inspect the screenshot alongside the measurements. Clear equal-width grid/flex rows are machine candidates; full-page symmetry, the Hero-plus-three-cards pattern and the meaning of any candidate still need actual visual interpretation.

Do not treat text left alignment, an offset decorative image, different colors, or a single wider active tab as substantive asymmetry. Check navigation/toolbars as well as content columns. A narrow-screen single-column form can keep a clear order; explain its composition and density rather than forcing horizontal imbalance that harms use. At each relevant width/state inspect whether meaningful content is visible, fixed elements cover it, or decoration overwhelms it. No horizontal overflow is only one condition and cannot establish these conclusions.

## Reference composition and density

Identify the selected reference's recognizable structural relationships in design.md before implementation. Describe the relative space assigned to main content and its action, their adjacency, embedded status/progress, connected or overlapping surfaces, edge profiles and reading sequence. Map each adopted relationship to actual page selectors and the narrow-screen arrangement. For an interview reference with a wide training module and a narrow action entry, keep their intended grouping and embedded progress when applying that composition to the page. Use other relationships when the selected direction calls for them.

Compare the first implemented major region against those relationships at the target viewport. Check the combined content/action hierarchy, progress placement, local lighting and surface edges. Record any content or accessibility adaptation and its visual effect. Repair a structural deviation before expanding the same component pattern into other regions.

Set body and necessary explanation sizes from the project's reading conditions and verify them with real text at the intended device size. Maintain compact density by removing repeated copy, merging related hints and adjusting gaps, line height and grouping. Check that labels, status and error feedback remain readable at the chosen size and during browser text enlargement. Record the actual values, contrast and reading observations for the affected selectors in typography, readability and layout review.
