## 2023-10-27 - [Password Toggle Absolute Positioning Conflict]
**Learning:** When adding interactive buttons with nested FontAwesome icons inside absolute positioned input wrappers (`.input-wrapper i`), the global CSS override applies absolute positioning to *all* child `<i>` tags, inadvertently breaking the layout of the inner icon.
**Action:** Apply an inline style (`position: static; transform: none;`) to the inner FontAwesome icon to prevent inheritance of absolute positioning from the wrapper's generic child selectors.
