"""Centralized stylesheet and color tokens for the Duplicate File Detector.

Maintains a consistent, sleek dark theme across all UI components.
"""

# Color Palette Constants
BG_WINDOW = "#17181b"
BG_SIDEBAR = "#222429"
BG_CARD = "#202226"
BG_CARD_INNER = "#292c32"
BG_HOVER = "#34373e"
BG_SELECTED = "#41444c"
BG_INPUT = "#2c2f36"

TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#e8e8e8"
TEXT_MUTED = "#92959c"
TEXT_SUBTLE = "#858991"
TEXT_DIM = "#b5b7bd"

BORDER_DEFAULT = "#34373e"
BORDER_LIGHT = "#41444c"

COLOR_ACCENT = "#3d7bf0"
COLOR_ACCENT_HOVER = "#508cf7"

COLOR_KEEP_TEXT = "#75d6aa"
COLOR_KEEP_BG = "#214b3b"
COLOR_KEEP_BORDER = "#2e6852"

COLOR_DUP_TEXT = "#ff958e"
COLOR_DUP_BG = "#542e30"
COLOR_DUP_BORDER = "#733e41"

COLOR_DANGER = "#a94444"
COLOR_DANGER_HOVER = "#c65353"

# Application-wide QSS
MAIN_STYLESHEET = f"""
QMainWindow {{
    background-color: {BG_WINDOW};
}}

QWidget {{
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
}}

/* Custom dark scrollbar */
QScrollBar:vertical {{
    border: none;
    background: #1a1b1e;
    width: 8px;
    margin: 0px 0px 0px 0px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: #3b3e47;
    min-height: 25px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #525663;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: #1a1b1e;
    height: 8px;
    margin: 0px 0px 0px 0px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: #3b3e47;
    min-width: 25px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #525663;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
"""
