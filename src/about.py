# about.py
#
# About dialog. Shows version, author, credits, and license.

import platform
import sys
import tkinter as tk
from tkinter import ttk

from src import version


class AboutDialog:
    def __init__(self, parent, lang):
        self.parent = parent
        self.lang = lang

        self.top = tk.Toplevel(parent)
        self.top.title(self.t("about.title"))
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)

        self._build()
        self.top.wait_window()

    def t(self, key, **fmt):
        return self.lang(key, **fmt)

    def _build(self):
        pad = {"padx": 14, "pady": 6}

        header = ttk.Frame(self.top)
        header.pack(fill="x", **pad)
        ttk.Label(header, text=version.APP_NAME,
                  font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        ttk.Label(header, text=f"v{version.VERSION}").pack(anchor="w")

        author_frame = ttk.LabelFrame(self.top, text=self.t("about.author"))
        author_frame.pack(fill="x", **pad)
        ttk.Label(author_frame, text=version.AUTHOR).pack(anchor="w",
                                                          padx=8, pady=2)
        link = ttk.Label(author_frame, text=version.AUTHOR_URL,
                         foreground="#3a6ea5", cursor="hand2")
        link.pack(anchor="w", padx=8, pady=(0, 4))
        link.bind("<Button-1>", lambda e: self._open_url(version.AUTHOR_URL))

        project_frame = ttk.LabelFrame(self.top, text=self.t("about.project"))
        project_frame.pack(fill="x", **pad)
        proj_link = ttk.Label(project_frame, text=version.PROJECT_URL,
                              foreground="#3a6ea5", cursor="hand2")
        proj_link.pack(anchor="w", padx=8, pady=2)
        proj_link.bind("<Button-1>",
                       lambda e: self._open_url(version.PROJECT_URL))

        credits_frame = ttk.LabelFrame(self.top, text=self.t("about.credits"))
        credits_frame.pack(fill="x", **pad)

        credit_text = tk.Text(credits_frame, height=7, wrap="word",
                              relief="flat", borderwidth=0,
                              highlightthickness=0)
        credit_text.pack(fill="x", padx=8, pady=4)

        credit_text.insert(tk.END, f"{version.PROTOCOL_CREDIT_NAME}\n", "name")
        credit_text.insert(tk.END,
                           f"{version.PROTOCOL_CREDIT_URL}\n\n", "link")
        credit_text.insert(tk.END, version.PROTOCOL_CREDIT_TEXT + "\n\n")
        credit_text.insert(tk.END, self.t("about.third_party") + "\n")
        for name, url in version.THIRD_PARTY:
            credit_text.insert(tk.END, f"  {name} — {url}\n")

        credit_text.tag_configure("name", font=("TkDefaultFont", 10, "bold"))
        credit_text.tag_configure("link", foreground="#3a6ea5")
        credit_text.configure(state="disabled")

        license_frame = ttk.LabelFrame(self.top, text=self.t("about.license"))
        license_frame.pack(fill="x", **pad)
        ttk.Label(license_frame, text=version.LICENSE).pack(anchor="w",
                                                            padx=8, pady=4)

        btns = ttk.Frame(self.top)
        btns.pack(fill="x", **pad)

        ttk.Button(btns, text=self.t("about.copy"),
                   command=self._copy_diag).pack(side="left", padx=4)
        ttk.Button(btns, text=self.t("about.close"),
                   command=self.top.destroy).pack(side="right", padx=4)

    def _open_url(self, url):
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _copy_diag(self):
        info = (
            f"{version.version_string()}\n"
            f"OS: {platform.system()} {platform.release()} "
            f"({platform.version()})\n"
            f"Python: {sys.version.split()[0]}\n"
            f"Architecture: {platform.machine()}\n"
            f"Repo: {version.PROJECT_URL}\n"
        )
        try:
            self.top.clipboard_clear()
            self.top.clipboard_append(info)
            self.top.update()
        except tk.TclError:
            pass