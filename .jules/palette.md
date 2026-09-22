## 2024-08-14 - Accessibility improvements for icon buttons
**Learning:** Found several icon-only links across the application (like footer social links, floating action buttons, and author social links) that were missing `aria-label` attributes. This makes them inaccessible to screen reader users, who will just hear the link URL or "link" without context.
**Action:** Always add descriptive `aria-label` attributes to anchor tags or buttons when they only contain icons.

## 2024-08-16 - Add proper label associations to inline forms
**Learning:** Found an accessibility pattern where standalone auth forms have proper labels but inline or custom-styled forms on marketing pages miss them (lacking `for` and `id` attributes).
**Action:** Always ensure every form input or interactive element is programmatically associated with its `label` via `for` and `id` tags.

## 2026-08-16 - Preserve Icons on Button State Changes
**Learning:** When using innerText to update button loading states, child icon elements (<i class="fas...">) are destroyed and often not restored properly.
**Action:** Always use innerHTML or explicitly target a text span inside the button to preserve icons during loading states, and ensure proper disabled visual feedback.

## 2026-08-19 - Standardizing Async/Sync Button Loading States
**Learning:** When implementing loading states on standard synchronous forms (like login or payment), adding a disabled state with a FontAwesome spinner provides immediate visual feedback and prevents duplicate submissions while the server processes the request.
**Action:** Apply this pattern to all standard form submit buttons across the application using `disabled` and `innerHTML`.
## 2026-09-22 - Adding custom keyframe animations in inline templates
**Learning:** When injecting `<style>` blocks for custom animations (like `@keyframes spin`) directly into Python inline templates using `render_template_string`, no special escaping is needed for the CSS block itself, but they should be placed safely within the body to prevent breaking existing layouts, especially when external stylesheet links aren't trivially editable.
**Action:** Always include scoped or globally unique animation names when injecting CSS dynamically to avoid naming collisions with external stylesheets.
