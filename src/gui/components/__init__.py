from importlib import import_module

from PySide6.QtGui import QColor

# Quality colors for light and dark themes.
QUALITY_COLORS = {
    "标准": (QColor("#606060"), QColor("#D0D0D0")),
    "非凡": (QColor("#1E9E00"), QColor("#2ECC71")),
    "稀有": (QColor("#007ACC"), QColor("#3498DB")),
    "史诗": (QColor("#8A2BE2"), QColor("#9B59B6")),
    "传奇": (QColor("#FF8C00"), QColor("#F39C12")),
    "传说": (QColor("#FF8C00"), QColor("#F39C12")),
}

_COMPONENT_EXPORTS = {
    "BannerWidget": ("src.gui.components.banner_widget", "BannerWidget"),
    "DashboardWidget": ("src.gui.components.dashboard_widget", "DashboardWidget"),
    "DateRangeCalendar": (
        "src.gui.components.date_range_picker",
        "DateRangeCalendar",
    ),
    "DateRangeDialog": ("src.gui.components.date_range_picker", "DateRangeDialog"),
    "DateRangePicker": ("src.gui.components.date_range_picker", "DateRangePicker"),
    "FilterDrawer": ("src.gui.components.filter_drawer", "FilterDrawer"),
    "FilterPanel": ("src.gui.components.filter_panel", "FilterPanel"),
    "FishPreviewWidget": (
        "src.gui.components.fish_preview_widget",
        "FishPreviewWidget",
    ),
    "FooterWidget": ("src.gui.components.footer_widget", "FooterWidget"),
    "KeyBindingWidget": (
        "src.gui.components.key_binding_widget",
        "KeyBindingWidget",
    ),
    "LogWidget": ("src.gui.components.log_widget", "LogWidget"),
}

__all__ = [
    "BannerWidget",
    "DashboardWidget",
    "DateRangeCalendar",
    "DateRangeDialog",
    "DateRangePicker",
    "FilterDrawer",
    "FilterPanel",
    "FishPreviewWidget",
    "FooterWidget",
    "KeyBindingWidget",
    "LogWidget",
    "QUALITY_COLORS",
]


def __getattr__(name):
    if name not in _COMPONENT_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _COMPONENT_EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
