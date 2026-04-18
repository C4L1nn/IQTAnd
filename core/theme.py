from .constants import THEMES, CURRENT_THEME


def get_accent() -> str:
    return THEMES.get(CURRENT_THEME, THEMES["Yeşil"])["accent"]


def get_accent_hover() -> str:
    return THEMES.get(CURRENT_THEME, THEMES["Yeşil"])["accent_hover"]


def get_glow() -> str:
    return THEMES.get(CURRENT_THEME, THEMES["Yeşil"])["glow"]
