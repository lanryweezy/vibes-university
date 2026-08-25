## 2024-08-14 - Accessibility improvements for icon buttons
**Learning:** Found several icon-only links across the application (like footer social links, floating action buttons, and author social links) that were missing `aria-label` attributes. This makes them inaccessible to screen reader users, who will just hear the link URL or "link" without context.
**Action:** Always add descriptive `aria-label` attributes to anchor tags or buttons when they only contain icons.

## 2024-08-16 - Add proper label associations to inline forms
**Learning:** Found an accessibility pattern where standalone auth forms have proper labels but inline or custom-styled forms on marketing pages miss them (lacking `for` and `id` attributes).
**Action:** Always ensure every form input or interactive element is programmatically associated with its `label` via `for` and `id` tags.

## 2026-08-16 - Preserve Icons on Button State Changes
**Learning:** When using innerText to update button loading states, child icon elements (<i class="fas...">) are destroyed and often not restored properly.
**Action:** Always use innerHTML or explicitly target a text span inside the button to preserve icons during loading states, and ensure proper disabled visual feedback.

## 2026-08-21 - Form Autocomplete & Mobile Input Optimization
**Learning:** Adding correct `autocomplete` attributes (like `email`, `name`, `tel`, `current-password`) and using appropriate HTML5 input types (like `type="tel"` instead of `type="text"`) significantly improves mobile user experience. Using `type="tel"` triggers the numeric keypad on mobile devices, preventing users from having to switch keyboards manually, while `autocomplete` allows browsers to accurately fill in data, reducing friction during checkout or login.
**Action:** Always include the correct `autocomplete` attribute on form fields, and strictly use `type="email"`, `type="tel"`, and `type="number"` where appropriate instead of defaulting to `type="text"` to ensure the best possible mobile input experience.

## 2026-08-25 - Fix event delegation and button state UX
**Learning:** Adding an `<i>` element inside a button can cause `event.target` to incorrectly refer to the icon when clicked directly, breaking event handlers and disabling logic that assume the button is the target. Using innerText for state changes also destroys the icon structure completely.
**Action:** Always use `event.target.closest('button')` instead of `event.target` when dealing with buttons containing child elements. When updating button states, use `innerHTML` to maintain icons and explicitly manage CSS disabled states rather than just HTML properties.
