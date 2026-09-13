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

## 2024-11-20 - Explicit Required Indicators & Focus Rings
**Learning:** Found that some forms lacked explicit visual indicators for required fields (relying only on HTML5 validation) and had poor focus visibility for keyboard navigation. High-contrast focus rings and visual `*` indicators are essential for a11y.
**Action:** Always include a visual required indicator (e.g., a red asterisk with aria-hidden="true") in the <label> of mandatory form fields, and provide a clear, high-contrast focus ring (such as a box-shadow) for interactive elements to improve accessibility and keyboard navigation.
## 2024-08-30 - High-Contrast Focus Rings & Required Indicators
**Learning:** Found that custom-styled input fields often lose standard browser focus rings, harming keyboard accessibility, and required fields lack clear visual indicators (like red asterisks) even if they have the `required` attribute.
**Action:** Always include a visual required indicator (e.g., a red asterisk with `aria-hidden="true"`) in the `<label>` of mandatory form fields, and provide a clear, high-contrast focus ring (such as a `box-shadow`) for interactive elements to improve accessibility and keyboard navigation.

## 2026-09-10 - Password Field Toggle Architecture and Label A11y
**Learning:** Adding interactive buttons containing FontAwesome icons within global `.input-wrapper i` wrappers creates layout breakages because of absolutely-positioned child selectors. Furthermore, adding interactive elements requires dynamic updates to `aria-label` based on current state to remain accessible. Additionally, `page.get_by_label()` and generic `page.click()` fail for layered UI elements inside these input wrappers.
**Action:** Always apply `position: static; transform: none;` overrides to icons nested in interactive wrapper buttons. Use `event.currentTarget` for dynamic element logic to ensure child elements don't steal the event target. During Playwright testing, explicitly use `page.evaluate("document.getElementById('elementId').click()")` to trigger clicks on visually layered wrapper elements to bypass "Element is outside of the viewport" Playwright strict mode errors.

## 2024-08-16 - Add proper label associations to profile forms
**Learning:** Found an accessibility pattern where the profile form was missing explicit `for` and `id` attributes associating the labels and input fields.
**Action:** Always ensure every form input or interactive element is programmatically associated with its `label` via matching `for` and `id` attributes.

## 2024-08-30 - High-Contrast Focus Rings & Required Indicators for profile form
**Learning:** Found that custom-styled input fields on the profile page lose standard browser focus rings, harming keyboard accessibility, and required fields lack clear visual indicators (like red asterisks) even if they have the `required` attribute.
**Action:** Always include a visual required indicator (e.g., a red asterisk with `aria-hidden="true"`) in the `<label>` of mandatory form fields, and provide a clear, high-contrast focus ring (such as a `box-shadow`) for interactive elements to improve accessibility and keyboard navigation.
