"""El Cami look, always light. Normally these come from .streamlit/config.toml;
if that file is missing (it's easy to forget when uploading, because the Mac
hides folders starting with a dot), the app applies them itself."""
from streamlit import config

THEME = {
    "theme.base": "light",
    "theme.font": "Inter:https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap",
    "theme.headingFontWeights": 600,
    "theme.baseFontSize": 16,
    "theme.primaryColor": "#0a523a",
    "theme.backgroundColor": "#eeeeee",
    "theme.secondaryBackgroundColor": "#ffffff",
    "theme.textColor": "#000000",
    "theme.linkColor": "#0a523a",
    "theme.linkUnderline": True,
    "theme.borderColor": "#808080",
    "theme.showWidgetBorder": True,
    "theme.baseRadius": "0",
    "theme.buttonRadius": "0",
    "theme.redColor": "#000000",
    "theme.redBackgroundColor": "#e9ff5e",
    "theme.redTextColor": "#000000",
    "theme.yellowBackgroundColor": "#e9ff5e",
    "theme.yellowTextColor": "#000000",
    "theme.blueBackgroundColor": "#d6e2e2",
    "theme.blueTextColor": "#000000",
    "theme.greenBackgroundColor": "#d6e2e2",
    "theme.greenTextColor": "#0a523a",
    "theme.sidebar.backgroundColor": "#d6e2e2",
    "theme.sidebar.secondaryBackgroundColor": "#ffffff",
    "theme.sidebar.textColor": "#000000",
    "theme.sidebar.borderColor": "#808080",
    "client.toolbarMode": "minimal",
}


def apply() -> bool:
    """Fills in any theme setting that isn't set. Returns True if something changed,
    in which case the page must reload once to pick it up."""
    changed = False
    for key, value in THEME.items():
        try:
            if config.get_option(key) is None or (key == "theme.base" and config.get_option(key) != "light"):
                config.set_option(key, value, "theme.py")
                changed = True
        except Exception:
            pass  # an option this Streamlit version doesn't know
    return changed
