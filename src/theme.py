# theme.py
#
# Appearance handling. Tries sv-ttk first (Windows 11 look, proper dark),
# falls back to a hand-rolled clam-based dark theme if sv-ttk is missing.
#
# After applying the theme we explicitly set the root background so that
# area around ttk widgets doesn't show through as system white.

import sys
import tkinter as tk
from tkinter import ttk


def _system_prefers_dark():
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except Exception:
        return False


def _try_sv_ttk(root, theme):
    try:
        import sv_ttk
    except ImportError:
        return False
    try:
        sv_ttk.set_theme(theme)
        return True
    except Exception:
        return False


def _apply_clam_dark(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        return

    bg        = "#1e1e1e"
    bg_alt    = "#252525"
    fg        = "#e6e6e6"
    fg_dim    = "#a0a0a0"
    border    = "#3a3a3a"
    select_bg = "#3a6ea5"
    select_fg = "#ffffff"
    entry_bg  = "#2a2a2a"
    button_bg = "#333333"
    button_hi = "#3f3f3f"

    root.configure(bg=bg)

    style.configure(".",
                    background=bg, foreground=fg,
                    fieldbackground=entry_bg,
                    bordercolor=border,
                    lightcolor=bg_alt, darkcolor=bg_alt,
                    troughcolor=bg_alt)

    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TLabelframe", background=bg, foreground=fg,
                    bordercolor=border)
    style.configure("TLabelframe.Label", background=bg, foreground=fg)

    style.configure("TButton",
                    background=button_bg, foreground=fg,
                    bordercolor=border, focusthickness=0,
                    padding=(8, 4))
    style.map("TButton",
              background=[("active", button_hi), ("disabled", bg_alt)],
              foreground=[("disabled", fg_dim)])

    style.configure("TEntry",
                    fieldbackground=entry_bg, foreground=fg,
                    bordercolor=border)
    style.map("TEntry",
              fieldbackground=[("readonly", entry_bg)],
              foreground=[("readonly", fg)])

    style.configure("TCombobox",
                    fieldbackground=entry_bg, background=button_bg,
                    foreground=fg, arrowcolor=fg, bordercolor=border)
    style.map("TCombobox",
              fieldbackground=[("readonly", entry_bg)],
              foreground=[("readonly", fg)],
              background=[("active", button_hi)])

    style.configure("TNotebook", background=bg, bordercolor=border)
    style.configure("TNotebook.Tab",
                    background=bg_alt, foreground=fg_dim,
                    padding=(12, 6))
    style.map("TNotebook.Tab",
              background=[("selected", bg)],
              foreground=[("selected", fg)])

    style.configure("TCheckbutton", background=bg, foreground=fg)
    style.map("TCheckbutton",
              background=[("active", bg)],
              foreground=[("disabled", fg_dim)])

    style.configure("TRadiobutton", background=bg, foreground=fg)
    style.map("TRadiobutton",
              background=[("active", bg)],
              foreground=[("disabled", fg_dim)])

    style.configure("TSeparator", background=border)


def _read_theme_bg():
    """Ask ttk what the current TFrame background is."""
    try:
        style = ttk.Style()
        bg = style.lookup("TFrame", "background")
        if bg:
            return bg
    except tk.TclError:
        pass
    return None


def apply_theme(root, appearance):
    """
    appearance: "system" | "light" | "dark"
    Applies the requested theme and returns the effective one ("light"/"dark").
    """
    if appearance == "system":
        effective = "dark" if _system_prefers_dark() else "light"
    else:
        effective = appearance

    if _try_sv_ttk(root, effective):
        # sv-ttk sets ttk widget colors but doesn't always repaint the raw
        # Tk root. Set it explicitly from whatever TFrame reports, so the
        # padding area around ttk widgets matches the theme.
        bg = _read_theme_bg()
        if bg:
            try:
                root.configure(bg=bg)
            except tk.TclError:
                pass
        return effective

    # Fallback path
    if effective == "dark":
        _apply_clam_dark(root)
    else:
        try:
            ttk.Style(root).theme_use("vista")
        except tk.TclError:
            pass
        bg = _read_theme_bg()
        if bg:
            try:
                root.configure(bg=bg)
            except tk.TclError:
                pass
    return effective