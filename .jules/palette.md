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

## 2026-09-18 - Avoid CDN injection for minor UX improvements
**Learning:** Adding new external UI dependencies (like injecting FontAwesome via `<link>` CDN) purely for a single micro-interaction, such as a loading spinner on a form button, violates the strict boundary constraint of not introducing new UI dependencies. It also creates risks related to privacy, offline-availability, and latency where the font may not render quickly enough during synchronous form submission, leaving the spinner invisible.
**Action:** When updating button loading states via JavaScript, use `innerHTML` with text or emojis (e.g., `Unlocking ⏳`) instead of relying on external dependencies like FontAwesome. Also, ensure the query selector handles buttons safely (`querySelector('button[type="submit"], button:not([type])')`) to avoid `TypeError`.
## 2026-09-19 - Safe Button Selection on Forms
**Learning:** Broadening the query selector to include `button:not([type])` is risky because it can inadvertently select and disable earlier, unrelated buttons in the DOM (e.g., secondary "Cancel" or "Close" buttons that accidentally lack a type attribute). Additionally, substituting animated FontAwesome spinners for static emojis degrades the visual polish of loading states.
**Action:** When updating button loading states via JavaScript on form submission, use `event.submitter || this.querySelector('button[type="submit"]')` to accurately and securely target the specific button that triggered the submission, and prefer animated visual feedback (e.g., FontAwesome spinners) over static emojis to avoid degrading the user experience.
