from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
import os
import subprocess
import sys
import logging
import datetime
from dfpyre import *

VALS_PER_APPEND = 26

BG       = "#1a1a2e"
SURFACE  = "#16213e"
PANEL    = "#0f3460"
ACCENT   = "#e94560"
TEXT     = "#eaeaea"
SUBTEXT  = "#a0a0b0"
BTN_BG   = "#e94560"
BTN_FG   = "#ffffff"
ENTRY_BG = "#0d1b2a"

OBJ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "obj")

LOADER_TEMPLATE_CODE = "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"
def _parse_command_pairs(text: str) -> list:
    pairs = []
    mat_pattern = re.compile(r'transformation:\[([^\]]+)\]')
    bg_pattern  = re.compile(r'background:(-?\d+)')

    positions = [(m.start(), m) for m in mat_pattern.finditer(text)]
    for i, (pos, mat_m) in enumerate(positions):
        raw = mat_m.group(1)
        try:
            vals = [float(v.strip().rstrip('f')) for v in raw.split(',')]
        except ValueError:
            continue
        if len(vals) != 16:
            continue
        formatted = ','.join(
            str(int(v)) if v == int(v) else f"{v:.7g}"
            for v in vals
        )
        mat_str = f"[{formatted}]"

        next_pos = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        segment  = text[pos:next_pos]
        bg_m     = bg_pattern.search(segment)
        if bg_m:
            argb = int(bg_m.group(1)) & 0xFFFFFFFF
            r, g, b = (argb >> 16) & 0xFF, (argb >> 8) & 0xFF, argb & 0xFF
            color = f"#{r:02x}{g:02x}{b:02x}"
        else:
            color = None
        pairs.append((mat_str, color))
    return pairs


def parse_command(text: str) -> list:
    return [mat for mat, _ in _parse_command_pairs(text)]


def parse_command_colors(text: str) -> list:
    return [col for _, col in _parse_command_pairs(text)]


def compute_max_faces(max_blocks: int, max_funcs: int) -> int:
    appends = max(1, max_blocks - 1) * VALS_PER_APPEND * max_funcs
    return appends // 3


def build_df_functions(func_name: str, var_name: str,
                       str_list: list, max_blocks=26) -> list:
    appends_per_func = max(1, max_blocks - 1)
    val_chunks  = [str_list[i:i+VALS_PER_APPEND]
                   for i in range(0, len(str_list), VALS_PER_APPEND)]
    func_groups = [val_chunks[i:i+appends_per_func]
                   for i in range(0, len(val_chunks), appends_per_func)]
    funcs = []
    for fi, group in enumerate(func_groups):
        name      = func_name if fi == 0 else f"{func_name}_{fi}"
        next_name = f"{func_name}_{fi+1}" if fi+1 < len(func_groups) else None
        line_var  = Variable(var_name, scope="line")
        actions   = [SV.AppendValue(line_var, [String(s) for s in chunk])
                     for chunk in group]
        if next_name:
            actions.append(CallFunction(next_name, line_var))
        if fi == 0:
            funcs.append(Function(name,
                                  Parameter(var_name, ParameterType.VAR),
                                  is_hidden="False",
                                  codeblocks=actions,
                                  author="OBJ-DF"))
        else:
            funcs.append(Function(name,
                                  Parameter(var_name, ParameterType.VAR),
                                  is_hidden="True",
                                  codeblocks=actions,
                                  author="OBJ-DF"))
    return funcs


DIST_DIR = os.path.join(OBJ_DIR, "dist")

def open_mesher_window(parent):
    dist_index = os.path.join(DIST_DIR, "index.html")
    if not os.path.isfile(dist_index):
        messagebox.showerror(
            "Mesher Not Found",
            f"Could not find:\n{dist_index}\n\n"
            "Build it once with:\n  cd obj\n  npm install\n  npm run build")
        return
    subprocess.Popen([sys.executable, "mesher_viewer.py", DIST_DIR])


class CommandDFApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OBJ → DiamondFire")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(780, 580)

        self._build_ui()
        self._on_constraints_change()

    def _build_ui(self):
        hd = tk.Frame(self, bg=PANEL)
        hd.pack(fill="x")
        tk.Label(hd, text="OBJ → DiamondFire", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 14, "bold"), pady=12).pack(side="left", padx=16)
        tk.Label(hd, text="OBJ → DF",
                 bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=4)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.columnconfigure(0, weight=0, minsize=300)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left  = tk.Frame(body, bg=SURFACE)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = tk.Frame(body, bg=SURFACE)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        def section(parent, title):
            s = tk.LabelFrame(parent, text=f" {title} ", bg=SURFACE, fg=ACCENT,
                               font=("Segoe UI", 9, "bold"), bd=1, relief="groove")
            s.pack(fill="x", padx=10, pady=5)
            return s

        def entry_row(parent, label, var, cb=None):
            r = tk.Frame(parent, bg=SURFACE)
            r.pack(fill="x", padx=8, pady=2)
            tk.Label(r, text=label, bg=SURFACE, fg=SUBTEXT,
                     font=("Segoe UI", 9), width=18, anchor="w").pack(side="left")
            tk.Entry(r, textvariable=var, bg=ENTRY_BG, fg=TEXT,
                     insertbackground=TEXT, font=("Segoe UI", 9, "bold"),
                     relief="flat", bd=4, width=8).pack(side="left", padx=4)
            if cb:
                var.trace_add("write", lambda *_: cb())

        ms = section(left, "3D Mesher Tool")
        tk.Label(ms,
                 text="Generate /summon commands from 3D models\nusing the mesher tool:",
                 bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 9),
                 justify="left").pack(anchor="w", padx=8, pady=(6, 4))
        tk.Button(ms, text="⧉  Open Text Display Mesher",
                  bg=BTN_BG, fg=BTN_FG,
                  font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                  command=lambda: open_mesher_window(self),
                  padx=10, pady=7).pack(fill="x", padx=8, pady=(2, 10))

        ds = section(left, "DF Constraints")
        self._max_blocks_var = tk.StringVar(value="20")
        self._max_funcs_var  = tk.StringVar(value="6")
        entry_row(ds, "Blocks / func:", self._max_blocks_var, self._on_constraints_change)
        entry_row(ds, "Max functions:", self._max_funcs_var,  self._on_constraints_change)
        self._cap_label = tk.Label(ds, text="", bg=SURFACE, fg=ACCENT,
                                   font=("Segoe UI", 9, "bold"), anchor="w")
        self._cap_label.pack(fill="x", padx=8, pady=(2, 6))

        es = section(left, "Export")
        self._func_name_var = tk.StringVar(value="DrawModel")
        self._var_name_var  = tk.StringVar(value="ModelData")
        entry_row(es, "Function name:", self._func_name_var)
        entry_row(es, "List variable:",  self._var_name_var)

        self._btn_export = tk.Button(
            es, text="Send to DiamondFire",
            bg=BTN_BG, fg=BTN_FG,
            font=("Segoe UI", 10, "bold"), relief="flat",
            cursor="hand2", command=self._export_df,
            padx=10, pady=6)
        self._btn_export.pack(fill="x", padx=8, pady=(6, 4))

        self._btn_export_texture = tk.Button(
            es, text="Export as Texture List",
            bg=PANEL, fg=SUBTEXT,
            font=("Segoe UI", 9, "bold"), relief="flat",
            cursor="hand2", command=self._export_texture_list,
            padx=10, pady=5)
        self._btn_export_texture.pack(fill="x", padx=8, pady=(0, 4))

        self._btn_send_loader = tk.Button(
            es, text="Send Loader to DiamondFire",
            bg=PANEL, fg=SUBTEXT,
            font=("Segoe UI", 9, "bold"), relief="flat",
            cursor="hand2", command=self._send_loader,
            padx=10, pady=5)
        self._btn_send_loader.pack(fill="x", padx=8, pady=(0, 10))

        hdr = tk.Frame(right, bg=PANEL)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="Paste /summon Command", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold"), pady=8, padx=12).pack(side="left")
        self._info_label = tk.Label(hdr, text="", bg=PANEL, fg=SUBTEXT,
                                    font=("Segoe UI", 9))
        self._info_label.pack(side="left", padx=6)

        text_frame = tk.Frame(right, bg=SURFACE)
        text_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        self._text = tk.Text(text_frame, bg=ENTRY_BG, fg=TEXT,
                             insertbackground=TEXT,
                             font=("Consolas", 9), relief="flat", bd=6,
                             wrap="none")
        sb_y = tk.Scrollbar(text_frame, command=self._text.yview)
        sb_x = tk.Scrollbar(text_frame, orient="horizontal",
                             command=self._text.xview)
        self._text.configure(yscrollcommand=sb_y.set,
                              xscrollcommand=sb_x.set)
        sb_y.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")
        self._text.grid(row=0, column=0, sticky="nsew")
        self._text.bind("<KeyRelease>", self._on_text_change)
        self._text.bind("<<Paste>>",    lambda e: self.after(50, self._on_text_change))

        tk.Label(right, text="← Paste your /summon command(s) above, then click a send button",
                 bg=SURFACE, fg=SUBTEXT, font=("Segoe UI", 8),
                 anchor="w").grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 4))

        self._status_var = tk.StringVar(value="Ready — paste a command or open the mesher tool.")
        tk.Label(self, textvariable=self._status_var, bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 8), anchor="w", pady=4
                 ).pack(fill="x", side="bottom")

    def _get_constraints(self):
        try:    mb = max(2, int(self._max_blocks_var.get() or "2"))
        except: mb = 20
        try:    mf = max(1, int(self._max_funcs_var.get() or "1"))
        except: mf = 6
        return mb, mf

    def _on_constraints_change(self, *_):
        mb, mf = self._get_constraints()
        cap = compute_max_faces(mb, mf)
        self._cap_label.config(
            text=f"Capacity: {cap:,} triangles  ({cap*3:,} entities)")

    def _status(self, msg):
        self._status_var.set(msg)

    def _on_text_change(self, *_):
        raw = self._text.get("1.0", "end")
        pairs = _parse_command_pairs(raw)
        if pairs:
            colors = [c for _, c in pairs if c]
            self._info_label.config(
                text=f"{len(pairs):,} matrices detected  |  {len(colors):,} colors")
        else:
            self._info_label.config(text="")

    def _get_parsed(self):
        """Parse the text box and return (strings, colors), or (None, None) if empty."""
        raw = self._text.get("1.0", "end")
        strings = parse_command(raw)
        if not strings:
            messagebox.showwarning("Nothing Found",
                                   "No transformation matrices found in the pasted text.")
            return None, None
        colors = [c for c in parse_command_colors(raw) if c is not None]
        return strings, colors

    def _check_entity_count(self, count: int) -> bool:
        """Return True if it's safe to proceed (either count is fine, or user confirmed)."""
        if count > 3900:
            return messagebox.askyesno(
                "⚠ High Entity Count!",
                f"DF normal plots have a max display entity limit of 4000.\n"
                f"You have {count:,} display entities.\n\n"
                f"Do you want to continue?",
                icon="warning")
        return True

    def _export_df(self):
        strings, colors = self._get_parsed()
        if strings is None:
            return
        if not self._check_entity_count(len(strings)):
            return
        func_name = self._func_name_var.get().strip() or "DrawModel"
        var_name  = self._var_name_var.get().strip()  or "ModelData"
        mb, _     = self._get_constraints()
        self._btn_export.config(state="disabled", text="Sending…")
        threading.Thread(target=self._do_export,
                         args=(func_name, var_name, strings, mb),
                         daemon=True).start()

    def _do_export(self, func_name, var_name, str_list, max_blocks):
        try:
            funcs = build_df_functions(func_name, var_name, str_list, max_blocks)
            self.after(0, self._status, f"Sending {len(funcs)} function(s)…")
            for i, f in enumerate(funcs):
                f.build_and_send()
                self.after(0, self._status, f"Sent {i+1}/{len(funcs)}…")
            self.after(0, self._on_export_done, len(funcs))
        except Exception as e:
            import traceback; traceback.print_exc()
            self.after(0, self._on_export_error, str(e))

    def _on_export_done(self, count):
        self._btn_export.config(state="normal", text="Send to DiamondFire")
        self._status(f"Done — {count} function(s) sent!")
        messagebox.showinfo("Done", f"Sent {count} function(s) to DiamondFire!")

    def _on_export_error(self, msg):
        self._btn_export.config(state="normal", text="Send to DiamondFire")
        self._status(f"Export failed: {msg}")
        messagebox.showerror("Export Error", f"Failed:\n\n{msg}")

    def _export_texture_list(self):
        strings, colors = self._get_parsed()
        if strings is None:
            return
        if not colors:
            messagebox.showwarning("No Colors",
                                   "No background colors found in the pasted command.")
            return
        if not self._check_entity_count(len(strings)):
            return
        func_name = (self._func_name_var.get().strip() or "DrawModel") + "_texture"
        var_name  = (self._var_name_var.get().strip()  or "ModelData")  + "_texture"
        mb, _     = self._get_constraints()
        self._btn_export_texture.config(state="disabled", text="Sending…")
        threading.Thread(target=self._do_export_texture,
                         args=(func_name, var_name, colors, mb),
                         daemon=True).start()

    def _do_export_texture(self, func_name, var_name, hex_list, max_blocks):
        try:
            funcs = build_df_functions(func_name, var_name, hex_list, max_blocks)
            self.after(0, self._status, f"Sending {len(funcs)} texture function(s)…")
            for i, f in enumerate(funcs):
                f.build_and_send()
                self.after(0, self._status, f"Sent {i+1}/{len(funcs)}…")
            self.after(0, self._on_texture_export_done, len(funcs))
        except Exception as e:
            self.after(0, self._on_texture_export_error, str(e))

    def _on_texture_export_done(self, count):
        self._btn_export_texture.config(state="normal", text="Export as Texture List")
        self._status(f"Done — {count} texture function(s) sent!")
        messagebox.showinfo("Done", f"Sent {count} texture function(s) to DiamondFire!")

    def _on_texture_export_error(self, msg):
        self._btn_export_texture.config(state="normal", text="Export as Texture List")
        self._status(f"Texture export failed: {msg}")
        messagebox.showerror("Export Error", f"Failed:\n\n{msg}")

    def _send_loader(self):
        if not LOADER_TEMPLATE_CODE:
            messagebox.showwarning("No Loader",
                                   "LOADER_TEMPLATE_CODE is empty.\n\n"
                                   "Set it at the top of the script.")
            return
        self._btn_send_loader.config(state="disabled", text="Sending…")
        threading.Thread(target=self._do_send_loader, daemon=True).start()

    def _do_send_loader(self):
        try:
            t = DFTemplate.from_code(LOADER_TEMPLATE_CODE)
            t.build_and_send()
            self.after(0, self._on_loader_done)
        except Exception as e:
            self.after(0, self._on_loader_error, str(e))

    def _on_loader_done(self):
        self._btn_send_loader.config(state="normal", text="Send Loader to DiamondFire")
        self._status("Done — loader sent!")
        messagebox.showinfo("Done", "Loader sent to DiamondFire!")

    def _on_loader_error(self, msg):
        self._btn_send_loader.config(state="normal", text="Send Loader to DiamondFire")
        self._status(f"Loader send failed: {msg}")
        messagebox.showerror("Export Error", f"Failed:\n\n{msg}")


if __name__ == "__main__":
    try:
        app = CommandDFApp()
        ttk.Style(app).theme_use("clam")
        app.mainloop()
    except Exception:
        import traceback; traceback.print_exc()
        input("Press Enter to close...")