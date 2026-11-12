# Interactions and motion

- Map affected flows and states: success, validation, loading, failure, empty content, overlays and dynamic feedback where present. No requirement to invent states a product does not have.
- Use semantic controls and accessible labels. Test focus movement, keyboard operation, escape/close behavior and restoration of focus when relevant.
- Applicable motion must avoid linear timing and ease-in-out; use suitable spring/custom nonlinear curves. Respect reduced-motion preferences and avoid blocking input.
- Test real interactions in the application. Screenshot presence, focus existence or a successful click call alone does not prove a flow completed correctly; assert the expected result.
- Browser viewport resizing does not verify a physical mobile keyboard. Real-device checks, simulated layout checks and unverified device behavior must be distinguished.
- Preserve authorization boundaries for external operations. Demo controls must not imply real account, SMS or backend integration when absent from scope.

New pages and full redesigns plan task-serving dynamic components per page in design.md. Show real content/state transitions with touch and keyboard support. Record trigger, before/after states, timing/easing, reduced-motion treatment and an executable action/result sequence. A static image, background movement or generic hover alone cannot establish this behavior. See design-document.md.

## Button feedback

Start from suitable StyleKit component and motion resources. Adapt feedback to the selected material and action hierarchy. Describe how hover, visible focus and press affect the button's surface, edge, shape, emphasis or content, and how the completed action updates the surrounding interface. For example, a hard-shadow button can lift on hover and compress its shadow on press; a soft tactile surface can deform briefly and recover with a spring. Select a coherent treatment rather than adding every effect. Keep primary, secondary and destructive actions recognizable within one component family; a universal opacity change alone leaves the requested button treatment incomplete.

Plan loading, success, error and disabled feedback where the actual operation has those states. Drive asynchronous feedback from the real pending/result/error state, preserve understandable labels and prevent accidental duplicate submission when needed. Test touch and keyboard behavior together with reduced-motion handling.

L3 whole-page work records design_plan.button_feedback entries with selector, page, trigger, states, visual_response, motion, reduced_motion and verification. verification contains page, width, state and steps. Its visual sequence uses remember_style on the button, an actual input and expect_style_changed. Task-serving dynamic_components separately use remember_state, an actual input and expect_state_changed for the operation result; both sequences may run in one browser case. Asynchronous assertions wait for the actual result. A successful click followed by finding the same unchanged button is insufficient. An interface without buttons records button_feedback_reason instead of inventing controls.

Verify the visible feedback separately from the action result: use remember_style/expect_style_changed around the planned hover or pointer action. Select the measured property for the actual feedback, such as transform, boxShadow or backgroundColor. A text change does not prove a shadow moved, and a transform change does not prove submission completed. Compare screenshots for material/shape quality, run the real action and verify its result, then verify the relevant keyboard, touch and reduced-motion paths. Reduced motion may remove displacement while retaining focus, press and pending/result feedback. L1/L2 work verifies the affected controls and states.

## Device and accessibility evidence

For affected flows, define the complete focus route across navigation, primary actions, forms, validation, overlays and return paths that exist in the interface. Operate forward and reverse traversal, activation, Escape/close and focus restoration as applicable. Record visible focus, logical order and any trapped, lost, obscured or unreachable control with the tested page/state and viewport.

Record physical touchscreen checks with the actual device, OS and browser, tested gestures, target selection, scrolling, keyboard appearance and overlay behavior relevant to the task. Keep browser touch emulation labelled with its actual environment in the evidence.

Screen-reader checks record the actual reader/browser combination and observed reading order, control names, roles, values, instructions, errors, announcements and dialog focus for the affected flows. DOM attributes and browser accessibility inspection can support these checks. Mark any physical device, focus route or reader path that was unavailable or unexecuted as unverified/blocked, with the specific missing coverage. Update the implementation checklist with each executed result and evidence location before delivery.
