# Purple sidebar review

Isolated branch: `fix/recent-practice-and-purple-sidebar-20261105`.

The existing `.ui-brand-header` gradient ends at `#312e81` (88%). Both old dark sidebar backgrounds now use that exact color. All added CSS selectors are scoped to `stSidebar`; inner containers remain transparent, with purple secondary buttons, readable light labels, dark text on light controls, blue hover rings and yellow keyboard/select focus rings. Expanded account panels remain translucent purple. Main background and header gradient are unchanged.

Rendered at desktop 1440x1000 and mobile 390x900. See `desktop-purple-sidebar.png`, `mobile-purple-expanded.png`, `mobile-purple-controls.png`, `mobile-key-dropdown.png`, `mobile-account-expanded.png`, `mobile-purple-collapsed.png`. Computed sidebar RGB is (49,46,129); `computed-styles.json` records the actual rendered header gradient and button styles.

This commit contains styling and review evidence only. No sidebar state, navigation, song, Practice Key or persistence code changes belong to it. Restoration is a separate commit.
