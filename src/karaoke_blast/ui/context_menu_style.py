"""Shared stylesheet for application context menus."""

CONTEXT_MENU_STYLE = (
    "QMenu { background-color: #1e1e2e; color: white; border: 1px solid #5a5a72; }"
    "QMenu::item { color: white; padding: 6px 24px; }"
    "QMenu::item:selected { background-color: #e94560; color: white; }"
    "QMenu::item:selected:active { background-color: #e94560; color: white; }"
    "QMenu::item:disabled { color: #888; }"
)
