"""Shared stylesheet for application checkboxes."""

_INDICATOR_CHECKED = """
    border: 1px solid #e94560;
    background-color: #e94560;
"""

_INDICATOR_CHECKED_HOVER = """
    border: 1px solid #ff6b81;
    background-color: #ff6b81;
"""

CHECKBOX_STYLE = f"""
QCheckBox {{
    color: #b8b8c8;
    font-size: 12px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid #5a5a72;
    border-radius: 3px;
    background-color: #2d2d42;
}}
QCheckBox::indicator:hover {{
    border-color: #7a7a92;
}}
QCheckBox::indicator:checked {{
    {_INDICATOR_CHECKED}
}}
QCheckBox::indicator:checked:hover {{
    {_INDICATOR_CHECKED_HOVER}
}}
"""

CHECKBOX_STYLE_WHITE_LABEL = f"""
QCheckBox {{
    color: white;
    font-size: 12px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid #5a5a72;
    border-radius: 3px;
    background-color: #2d2d42;
}}
QCheckBox::indicator:hover {{
    border-color: #7a7a92;
}}
QCheckBox::indicator:checked {{
    {_INDICATOR_CHECKED}
}}
QCheckBox::indicator:checked:hover {{
    {_INDICATOR_CHECKED_HOVER}
}}
"""
