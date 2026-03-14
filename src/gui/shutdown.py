"""Helpers for shutting down GUI-owned background services."""


def _call_if_exists(target, method_name: str):
    if target is None:
        return

    method = getattr(target, method_name, None)
    if callable(method):
        method()


def shutdown_main_window_services(window, uno_manager=None):
    """Stop non-worker services so the app can exit cleanly."""
    _call_if_exists(window, "_save_overlay_state")
    _call_if_exists(getattr(window, "cycle_reset_manager", None), "stop")

    overlay = getattr(window, "overlay", None)
    if overlay is not None:
        close = getattr(overlay, "close", None)
        if callable(close):
            close()
        else:
            _call_if_exists(overlay, "hide")

    _call_if_exists(getattr(window, "input_controller", None), "stop_listening")
    _call_if_exists(uno_manager, "stop")
