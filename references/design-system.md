# Design system and visual direction

## Apply requirements to the actual task
- Preserve user-selected branding and existing systems for local changes. Do not repaint or rebuild unrelated pages. Explicit current user requirements take precedence over defaults; record concrete conflicts rather than silently ignoring them.
- New visual directions use deliberate, distinctive combinations of color, type, material and composition. Explore several directions, then keep the selected one coherent. No universal fixed font or palette is imposed on every project.

## Original mandatory requirements within the affected scope
- No purple, indigo, blue-violet gradients, including #6366F1 and #8B5CF6. Define custom colors instead of Tailwind default color tokens.
- Page backgrounds use noise, texture or a suitable gradient with the material character and intensity of the selected direction. Preserve readable contrast across actual text and component states.
- Avoid the Hero-plus-three-cards template, perfectly centered page composition and equal-width content columns. Use asymmetry, hierarchy and purposeful negative space; see layout.md.
- Select coordinated Chinese and Latin typefaces, with usable weights, sizes and spacing. Verify loaded fonts and small-screen readability.
- Read typography.md for the user's body-font restriction, role-based candidates, actual font resources, Chinese coverage and rendered-font evidence. Apply the selected body face to controls and component themes as appropriate.
- Use short, conversational, specific copy; no jargon, filler, Lorem Ipsum or fabricated product numbers. Allow humor when appropriate.
- Review copy by its contribution to understanding, decisions and actions. Remove redundant explanations and empty motivational slogans. Preserve complete necessary instructions, errors, brand names and agreements. Include dynamic and overlay states.
- Preserve original logos and user-owned content. Report a concrete conflict when immutable text violates a chosen requirement; do not rewrite it silently.

## Scope and evidence
- L1 applies relevant rules to changed content, not every pre-existing string/style in the application. L2 applies them to affected components/states. L3 visual work evaluates the declared pages as a coherent composition.
- `strict` is the default. `project` and `expressive` remain compatibility labels with exactly the same hard checks. L1/L2 reduce affected scope, never applicable requirements. A conflicting existing brand requires a concrete user decision; it is not an automatic exemption.
- Record actual tokens, type scale, material treatment and how imagery relates to the content. Judge the result in the real page, including contrast, crop and density. Static scans produce candidates, not aesthetic judgments.

## Regional color and material decisions

For L3 whole-page work, design_plan.visual_surfaces records selector, color_roles, material and reference_features for the significant page surfaces. In design.md map canvas, content surfaces, focal areas, ink and accent to actual tokens and their intended prominence. Describe the selected reference's lightness, saturation and warm/cool relationships, then compare the rendered regions against those choices.

Describe each material's layer order and implementation, including relevant texture source, grain scale/intensity, lighting direction, edges and shadows. Use values appropriate to the reference and each region's role. Avoid replacing every style with the same pale paper wash: preserve the selected direction's dark/light range, accent prominence, texture visibility and hard/soft edge treatment. A gradient with identical stops or a fully transparent texture layer does not supply a visible material.

First inspect one major region at the target display size with its real content and imagery, then carry the same material language into other regions. For each significant region record the expected reference features, observed colors/material, any deviation and its repair or necessary adaptation under reference_fidelity and materials. Distinguish an actual hue/value/material mismatch from a justified content or accessibility change. Matching token names or collecting computed CSS values cannot substitute for the screenshot comparison; whole-page pixel similarity is also unsuitable when content or responsive composition differs.

L1/L2 work applies these decisions to the affected regions. An explicit text user_custom direction supplies the reference features when no image was selected. Reference exploration retains its lightweight four-image selection flow.

## Surface hierarchy and expressive type

Translate the reference's curved, inset, raised or connected surfaces into component-level material decisions. Record which surface leads the main task, where local light falls, how rim highlights and contact shadows define depth, and how adjacent components differ in tone, edge and elevation. Inspect these relationships with actual controls and content in place. Preserve their visibility at the chosen viewport and verify text contrast over the resulting surfaces.

Explore expressive type suited to the selected visual direction for brand and display roles. Compare suitable serif, condensed, geometric, monospace or other artistic treatments using the actual page title and representative Chinese/Latin strings. Choose body and necessary instruction faces for reading. Record selected families, role, genuine available weights, Chinese fallback, loading method and license. Verify loaded glyphs, wrapping, line height and browser text enlargement on the actual page. Match the final choice to the selected direction and carry it into tokens and component overrides.
