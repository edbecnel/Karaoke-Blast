"""Shared stylesheet for application checkboxes."""

_CHECKMARK_SVG = (
    "data:image/svg+xml;charset=utf-8,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 14 14'%3E"
    "%3Crect width='14' height='14' rx='3' fill='%23e94560'/%3E"
    "%3Cpath d='M3.5 7.2 L5.8 9.5 L10.5 4.8' stroke='%23ffffff' stroke-width='1.6' "
    "fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E"
    "%3C/svg%3E"
)

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
    border: none;
    background: transparent;
    image: url({_CHECKMARK_SVG});
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
    border: none;
    background: transparent;
    image: url({_CHECKMARK_SVG});
}}
"""
