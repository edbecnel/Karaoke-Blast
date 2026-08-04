"""Shared QListWidget styles for sidebar lists."""

LIST_ITEM_INTERACTION_STYLE = """
QListWidget::item {
    color: white;
}
QListWidget::item:selected {
    background-color: rgba(233, 69, 96, 120);
    color: white;
}
QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 30);
    color: white;
}
QListWidget::item:selected:hover {
    background-color: rgba(233, 69, 96, 140);
    color: white;
}
QListWidget::item:selected:active {
    background-color: rgba(233, 69, 96, 140);
    color: white;
}
"""

SIDEBAR_LIST_STYLE = (
    """
QListWidget {
    background-color: rgba(20, 20, 30, 230);
    color: white;
    selection-color: white;
    selection-background-color: rgba(233, 69, 96, 120);
    border: none;
    font-size: 13px;
    outline: none;
}
QListWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 20);
}
"""
    + LIST_ITEM_INTERACTION_STYLE
)

QUEUE_LIST_STYLE = (
    """
QListWidget {
    background-color: rgba(20, 20, 30, 120);
    color: white;
    selection-color: white;
    selection-background-color: rgba(233, 69, 96, 120);
    border: none;
    font-size: 12px;
    outline: none;
}
QListWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 15);
}
"""
    + LIST_ITEM_INTERACTION_STYLE
)

RECENT_FOLDERS_LIST_STYLE = (
    """
QListWidget {
    background-color: rgba(255, 255, 255, 12);
    color: white;
    selection-color: white;
    selection-background-color: rgba(233, 69, 96, 140);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 6px;
    font-size: 13px;
    outline: none;
    padding: 4px;
}
QListWidget::item {
    padding: 10px 12px;
    border-radius: 4px;
}
"""
    + LIST_ITEM_INTERACTION_STYLE
)
