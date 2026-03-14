import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
import threading
from PIL import Image, ImageTk
import math

from dfpyre import *

MAX_COLOR_STOPS  = 6
PREVIEW_MAX_W    = 420
PREVIEW_MAX_H    = 280
VALS_PER_APPEND  = 26
ZOOM_MIN         = 0.1
ZOOM_MAX         = 16.0
ZOOM_STEP        = 1.15

BG       = "#1a1a2e"
SURFACE  = "#16213e"
PANEL    = "#0f3460"
ACCENT   = "#e94560"
TEXT     = "#eaeaea"
SUBTEXT  = "#a0a0b0"
BTN_BG   = "#e94560"
BTN_FG   = "#ffffff"
ENTRY_BG = "#0d1b2a"

STOP_COLORS = ["#ff4444", "#ff9944", "#ffff44", "#44ff44", "#44aaff", "#aa44ff"]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"

def lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def brightness(pixel):
    if isinstance(pixel, int):
        return pixel
    r, g, b = pixel[:3]
    return int(0.299*r + 0.587*g + 0.114*b)

def map_brightness_to_color(bval, stops):
    if not stops:
        return rgb_to_hex(bval, bval, bval)
    if bval <= stops[0][0]:
        return stops[0][1]
    if bval >= stops[-1][0]:
        return stops[-1][1]
    for i in range(len(stops) - 1):
        lo_b, lo_c = stops[i]
        hi_b, hi_c = stops[i + 1]
        if lo_b <= bval <= hi_b:
            t = (bval - lo_b) / max(hi_b - lo_b, 1)
            return rgb_to_hex(*lerp_color(hex_to_rgb(lo_c), hex_to_rgb(hi_c), t))
    return stops[-1][1]

def compute_max_pixels(max_blocks, max_funcs):
    appends_per_func = max(1, max_blocks - 1)
    return appends_per_func * VALS_PER_APPEND * max_funcs

def process_image(img, stops, max_pixels=0):
    img_rgb = img.convert("RGB")
    if max_pixels and img_rgb.width * img_rgb.height > max_pixels:
        scale = math.sqrt(max_pixels / (img_rgb.width * img_rgb.height))
        new_w = max(1, int(img_rgb.width  * scale))
        new_h = max(1, int(img_rgb.height * scale))
        img_rgb = img_rgb.resize((new_w, new_h), Image.LANCZOS)
    pixels  = list(img_rgb.getdata())
    hexlist = [map_brightness_to_color(brightness(p), stops) for p in pixels]
    return hexlist, img_rgb.width, img_rgb.height

def build_preview_image(hex_list, w, h):
    img = Image.new("RGB", (w, h))
    img.putdata([hex_to_rgb(c) for c in hex_list])
    return img


def build_df_functions(func_name, var_name, hex_list, max_blocks=26):
    appends_per_func = max(1, max_blocks - 1)

    val_chunks  = [hex_list[i:i+VALS_PER_APPEND]
                   for i in range(0, len(hex_list), VALS_PER_APPEND)]
    func_groups = [val_chunks[i:i+appends_per_func]
                   for i in range(0, len(val_chunks), appends_per_func)]

    funcs = []
    for fi, group in enumerate(func_groups):
        name      = func_name if fi == 0 else f"{func_name}_{fi}"
        next_name = f"{func_name}_{fi+1}" if fi + 1 < len(func_groups) else None
        line_var  = Variable(var_name, scope="line")

        actions = []
        for chunk in group:
            actions.append(SV.AppendValue(line_var, [String(h) for h in chunk]))
        if next_name:
            actions.append(CallFunction(next_name, line_var))

        funcs.append(Function(
            name,
            Parameter(var_name, ParameterType.VAR),
            codeblocks=actions,
            author="NoiseMapTool"
        ))

    return funcs


class ColorStopRow(tk.Frame):
    def __init__(self, parent, index, threshold, color, on_delete, on_change, **kw):
        super().__init__(parent, bg=SURFACE, **kw)
        self._on_delete = on_delete
        self._on_change = on_change
        self._color     = color
        self._index     = index

        tk.Label(self, text=f"Stop {index+1}", bg=SURFACE, fg=SUBTEXT,
                 font=("Segoe UI", 9), width=6).pack(side="left", padx=(6, 2))

        self._thresh_var = tk.IntVar(value=threshold)
        ttk.Scale(self, from_=0, to=255, orient="horizontal",
                  variable=self._thresh_var, length=140,
                  command=lambda _: self._on_change()).pack(side="left", padx=4)

        tk.Label(self, textvariable=self._thresh_var,
                 bg=SURFACE, fg=TEXT, font=("Segoe UI", 9), width=4).pack(side="left")

        self._swatch = tk.Label(self, bg=color, width=4, relief="flat", cursor="hand2")
        self._swatch.pack(side="left", padx=6, ipady=6)
        self._swatch.bind("<Button-1>", self._pick_color)

        self._color_lbl = tk.Label(self, text=color, bg=SURFACE, fg=TEXT,
                                   font=("Courier", 9), width=8)
        self._color_lbl.pack(side="left")

        tk.Button(self, text="✕", bg=SURFACE, fg=ACCENT, relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2",
                  command=lambda: self._on_delete(self)).pack(side="left", padx=4)

    def _pick_color(self, _=None):
        result = colorchooser.askcolor(color=self._color, title="Pick Color")
        if result and result[1]:
            self._color = result[1].lower()
            self._swatch.config(bg=self._color)
            self._color_lbl.config(text=self._color)
            self._on_change()

    @property
    def threshold(self):
        return self._thresh_var.get()

    @property
    def color(self):
        return self._color


class NoiseMapApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Noise Map → DiamondFire")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(920, 640)

        self._image             = None
        self._preview_pil       = None
        self._preview_photo     = None
        self._stop_rows         = []
        self._hex_list          = []
        self._img_w = self._img_h = 0
        self._zoom              = 1.0
        self._pan_x = self._pan_y = 0
        self._drag_start        = None

        self._build_ui()
        self._add_default_stops()
        self.after(200, self._on_constraints_change)

    def _build_ui(self):
        top = tk.Frame(self, bg=PANEL, height=52)
        top.pack(fill="x")
        tk.Label(top, text="⬡  Noise Map → DiamondFire", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 14, "bold"), pady=12).pack(side="left", padx=16)
        tk.Label(top, text="Convert B&W noise textures to DF hex string lists",
                 bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="left", padx=4)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.columnconfigure(0, weight=0, minsize=330)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=SURFACE)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        img_sec = tk.LabelFrame(left, text=" Image ", bg=SURFACE, fg=ACCENT,
                                font=("Segoe UI", 9, "bold"), bd=1, relief="groove")
        img_sec.pack(fill="x", padx=10, pady=(10, 4))

        self._img_label = tk.Label(img_sec, text="No image loaded",
                                   bg=ENTRY_BG, fg=SUBTEXT, font=("Segoe UI", 9),
                                   wraplength=240, height=2)
        self._img_label.pack(fill="x", padx=8, pady=6)

        tk.Button(img_sec, text="📂  Load Image", bg=BTN_BG, fg=BTN_FG,
                  font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                  command=self._load_image, padx=8, pady=4
                  ).pack(fill="x", padx=8, pady=(0, 8))

        df_sec = tk.LabelFrame(left, text=" DF Constraints ", bg=SURFACE, fg=ACCENT,
                               font=("Segoe UI", 9, "bold"), bd=1, relief="groove")
        df_sec.pack(fill="x", padx=10, pady=(0, 4))

        self._max_blocks_var = tk.StringVar(value="26")
        self._max_funcs_var  = tk.StringVar(value="3")

        def _constraint_row(parent, label, var, tip=""):
            row = tk.Frame(parent, bg=SURFACE)
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=label, bg=SURFACE, fg=SUBTEXT,
                     font=("Segoe UI", 9), width=18, anchor="w").pack(side="left")
            vcmd = (self.register(lambda v: v.isdigit() or v == ""), "%P")
            tk.Entry(row, textvariable=var, bg=ENTRY_BG, fg=TEXT,
                     insertbackground=TEXT, font=("Segoe UI", 9, "bold"),
                     relief="flat", bd=4, width=6,
                     validate="key", validatecommand=vcmd
                     ).pack(side="left", padx=4)
            if tip:
                tk.Label(row, text=tip, bg=SURFACE, fg=SUBTEXT,
                         font=("Segoe UI", 8)).pack(side="left")
            var.trace_add("write", lambda *_: self._on_constraints_change())

        _constraint_row(df_sec, "Max blocks / func:", self._max_blocks_var,
                        "(AppendValues + call)")
        _constraint_row(df_sec, "Max functions:",     self._max_funcs_var)

        self._cap_label = tk.Label(df_sec, text="", bg=SURFACE, fg=ACCENT,
                                   font=("Segoe UI", 9, "bold"), anchor="w", justify="left")
        self._cap_label.pack(fill="x", padx=8, pady=(2, 6))

        stop_sec = tk.LabelFrame(left, text=" Color Stops  (low → high brightness) ",
                                 bg=SURFACE, fg=ACCENT,
                                 font=("Segoe UI", 9, "bold"), bd=1, relief="groove")
        stop_sec.pack(fill="both", expand=True, padx=10, pady=4)

        self._stops_frame = tk.Frame(stop_sec, bg=SURFACE)
        self._stops_frame.pack(fill="both", expand=True, padx=4, pady=4)

        add_row = tk.Frame(stop_sec, bg=SURFACE)
        add_row.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(add_row, text="＋ Add Stop", bg=PANEL, fg=TEXT,
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  command=self._add_stop, padx=6, pady=3).pack(side="left")
        tk.Label(add_row, text=f"(max {MAX_COLOR_STOPS})", bg=SURFACE, fg=SUBTEXT,
                 font=("Segoe UI", 8)).pack(side="left", padx=6)

        exp_sec = tk.LabelFrame(left, text=" Export ", bg=SURFACE, fg=ACCENT,
                                font=("Segoe UI", 9, "bold"), bd=1, relief="groove")
        exp_sec.pack(fill="x", padx=10, pady=(4, 10))

        def _name_row(parent, label, var):
            row = tk.Frame(parent, bg=SURFACE)
            row.pack(fill="x", padx=8, pady=4)
            tk.Label(row, text=label, bg=SURFACE, fg=SUBTEXT,
                     font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=var, bg=ENTRY_BG, fg=TEXT,
                     insertbackground=TEXT, font=("Segoe UI", 9),
                     relief="flat", bd=4).pack(side="left", fill="x", expand=True, padx=4)

        self._func_name_var = tk.StringVar(value="NoiseMap")
        self._var_name_var  = tk.StringVar(value="MapColors")
        _name_row(exp_sec, "Function name:", self._func_name_var)
        _name_row(exp_sec, "List variable:", self._var_name_var)

        self._btn_export = tk.Button(exp_sec, text="🚀  Send to DiamondFire",
                                     bg=BTN_BG, fg=BTN_FG,
                                     font=("Segoe UI", 10, "bold"), relief="flat",
                                     cursor="hand2", command=self._export_df,
                                     padx=10, pady=6)
        self._btn_export.pack(fill="x", padx=8, pady=(0, 10))

        right = tk.Frame(body, bg=SURFACE)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        prev_hdr = tk.Frame(right, bg=PANEL)
        prev_hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(prev_hdr, text="Preview", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold"), pady=8, padx=12).pack(side="left")
        self._info_label = tk.Label(prev_hdr, text="", bg=PANEL, fg=SUBTEXT,
                                    font=("Segoe UI", 9))
        self._info_label.pack(side="left", padx=6)
        self._zoom_label = tk.Label(prev_hdr, text="", bg=PANEL, fg=ACCENT,
                                    font=("Segoe UI", 9, "bold"))
        self._zoom_label.pack(side="left", padx=6)

        btn_frame = tk.Frame(prev_hdr, bg=PANEL)
        btn_frame.pack(side="right", padx=8)
        tk.Button(btn_frame, text="⟳ Reset Zoom", bg=PANEL, fg=SUBTEXT, relief="flat",
                  font=("Segoe UI", 9), cursor="hand2",
                  command=self._reset_zoom, padx=6, pady=4).pack(side="left", padx=4)
        tk.Button(btn_frame, text="↺ Refresh", bg=PANEL, fg=ACCENT, relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2",
                  command=self._refresh_preview, padx=8, pady=4).pack(side="left")

        self._canvas = tk.Canvas(right, bg=ENTRY_BG, highlightthickness=0, cursor="crosshair")
        self._canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        self._canvas.bind("<Control-MouseWheel>",  self._on_ctrl_scroll_win)
        self._canvas.bind("<Control-Button-4>",    self._on_ctrl_scroll_up)
        self._canvas.bind("<Control-Button-5>",    self._on_ctrl_scroll_down)
        self._canvas.bind("<ButtonPress-1>",   self._on_drag_start)
        self._canvas.bind("<B1-Motion>",       self._on_drag_move)
        self._canvas.bind("<ButtonRelease-1>", self._on_drag_end)

        self._legend_canvas = tk.Canvas(right, bg=SURFACE, height=50, highlightthickness=0)
        self._legend_canvas.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        self._status_var = tk.StringVar(value="Ready — load an image to begin.")
        tk.Label(self, textvariable=self._status_var, bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 8), anchor="w", pady=4).pack(fill="x", side="bottom")

    def _get_constraints(self):
        try:
            mb = max(2, int(self._max_blocks_var.get() or "2"))
        except ValueError:
            mb = 26
        try:
            mf = max(1, int(self._max_funcs_var.get() or "1"))
        except ValueError:
            mf = 3
        return mb, mf

    def _on_constraints_change(self):
        mb, mf = self._get_constraints()
        max_px = compute_max_pixels(mb, mf)
        appends_pf = max(1, mb - 1)
        self._cap_label.config(
            text=(f"Capacity: {max_px:,} pixels\n"
                  f"{appends_pf} AppendValues/func  ×  {mf} funcs  ×  {VALS_PER_APPEND} vals")
        )
        if self._image:
            self._refresh_preview()

    def _add_default_stops(self):
        for thresh, col in [(0,"#0d0d2b"),(90,"#1a3a6b"),(160,"#2e8b57"),(210,"#c8a32c"),(255,"#ffffff")]:
            self._add_stop(threshold=thresh, color=col)

    def _add_stop(self, threshold=None, color=None):
        if len(self._stop_rows) >= MAX_COLOR_STOPS:
            messagebox.showinfo("Max Stops", f"Maximum {MAX_COLOR_STOPS} color stops allowed.")
            return
        idx    = len(self._stop_rows)
        thresh = threshold if threshold is not None else min(255, idx * (255 // max(MAX_COLOR_STOPS-1,1)))
        col    = color    if color    is not None else STOP_COLORS[idx % len(STOP_COLORS)]
        row    = ColorStopRow(self._stops_frame, idx, thresh, col,
                              on_delete=self._remove_stop, on_change=self._on_stop_change)
        row.pack(fill="x", pady=2)
        self._stop_rows.append(row)
        self._on_stop_change()

    def _remove_stop(self, row):
        self._stop_rows.remove(row)
        row.destroy()
        for i, r in enumerate(self._stop_rows):
            r._index = i
        self._on_stop_change()

    def _on_stop_change(self, *_):
        self._draw_legend()
        if self._image:
            self._refresh_preview()

    def _get_sorted_stops(self):
        return sorted([(r.threshold, r.color) for r in self._stop_rows], key=lambda x: x[0])

    def _load_image(self):
        path = filedialog.askopenfilename(
            title="Open Noise Map",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tga *.tiff *.webp"), ("All", "*.*")]
        )
        if not path:
            return
        try:
            self._image = Image.open(path).convert("RGB")
            name = path.replace("\\","/").split("/")[-1]
            self._img_label.config(text=f"✓  {name}\n{self._image.width}×{self._image.height}")
            self._status("Image loaded: " + name)
            self._reset_zoom(redraw=False)
            self._refresh_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image:\n{e}")

    def _refresh_preview(self):
        if self._image is None:
            return
        self._status("Processing preview…")
        threading.Thread(target=self._do_preview, daemon=True).start()

    def _do_preview(self):
        stops  = self._get_sorted_stops()
        mb, mf = self._get_constraints()
        max_px = compute_max_pixels(mb, mf)
        hex_list, w, h = process_image(self._image, stops, max_pixels=max_px)
        self._hex_list = hex_list
        self._img_w, self._img_h = w, h
        self._preview_pil = build_preview_image(hex_list, w, h)
        self.after(0, self._redraw_canvas, len(hex_list), w, h)

    def _redraw_canvas(self, total_px=None, w=None, h=None):
        if self._preview_pil is None:
            return
        cw = max(self._canvas.winfo_width(),  1)
        ch = max(self._canvas.winfo_height(), 1)
        disp_w = max(1, int(self._preview_pil.width  * self._zoom))
        disp_h = max(1, int(self._preview_pil.height * self._zoom))
        resized = self._preview_pil.resize((disp_w, disp_h), Image.NEAREST if self._zoom >= 2 else Image.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(resized)
        self._canvas.delete("all")
        cx = cw // 2 + self._pan_x
        cy = ch // 2 + self._pan_y
        self._canvas.create_image(cx, cy, anchor="center", image=self._preview_photo)
        pct = int(self._zoom * 100)
        self._zoom_label.config(text=f"{pct}%")
        if total_px is not None:
            w = w or self._img_w
            h = h or self._img_h
            self._info_label.config(text=f"{w}×{h}  ({total_px:,} px → {total_px:,} hex values)")
            self._status(f"Preview ready — {total_px:,} hex values generated.  Ctrl+Scroll to zoom.")

    def _on_ctrl_scroll_win(self, event):
        if event.delta > 0:
            self._zoom_by(ZOOM_STEP)
        else:
            self._zoom_by(1 / ZOOM_STEP)

    def _on_ctrl_scroll_up(self, event):
        self._zoom_by(ZOOM_STEP)

    def _on_ctrl_scroll_down(self, event):
        self._zoom_by(1 / ZOOM_STEP)

    def _zoom_by(self, factor):
        new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, self._zoom * factor))
        if new_zoom == self._zoom:
            return
        self._zoom = new_zoom
        self._redraw_canvas()

    def _reset_zoom(self, redraw=True):
        self._zoom  = 1.0
        self._pan_x = 0
        self._pan_y = 0
        if redraw:
            self._redraw_canvas()

    def _on_drag_start(self, event):
        self._drag_start = (event.x, event.y)

    def _on_drag_move(self, event):
        if self._drag_start:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            self._pan_x += dx
            self._pan_y += dy
            self._drag_start = (event.x, event.y)
            self._redraw_canvas()

    def _on_drag_end(self, event):
        self._drag_start = None

    def _draw_legend(self):
        c = self._legend_canvas
        c.delete("all")
        stops = self._get_sorted_stops()
        if not stops:
            return
        W = max(c.winfo_width(), 300)
        for x in range(W):
            bval = int(x / max(W-1,1) * 255)
            c.create_line(x, 5, x, 32, fill=map_brightness_to_color(bval, stops))
        for thresh, col in stops:
            x = int(thresh / 255 * (W-1))
            c.create_line(x, 2, x, 35, fill="#ffffff", width=1)
            c.create_rectangle(x-4, 35, x+4, 45, fill=col, outline="#ffffff")
        c.create_text(2,   48, text="0",   fill=SUBTEXT, anchor="sw", font=("Segoe UI",7))
        c.create_text(W-2, 48, text="255", fill=SUBTEXT, anchor="se", font=("Segoe UI",7))

    def _export_df(self):
        if self._image is None:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        if not self._hex_list:
            messagebox.showwarning("No Data", "Refresh preview first.")
            return
        func_name = self._func_name_var.get().strip() or "NoiseMap"
        var_name  = self._var_name_var.get().strip()  or "MapColors"
        mb, _     = self._get_constraints()
        self._btn_export.config(state="disabled", text="Sending…")
        self._status("Building DiamondFire code…")
        threading.Thread(
            target=self._do_export,
            args=(func_name, var_name, list(self._hex_list), mb),
            daemon=True
        ).start()

    def _do_export(self, func_name, var_name, hex_list, max_blocks):
        try:
            funcs = build_df_functions(func_name, var_name, hex_list, max_blocks)
            self.after(0, self._status, f"Sending {len(funcs)} function(s) to DiamondFire…")
            for i, f in enumerate(funcs):
                f.build_and_send()
                self.after(0, self._status, f"Sent function {i+1}/{len(funcs)}…")
            self.after(0, self._on_export_done, len(funcs))
        except Exception as e:
            self.after(0, self._on_export_error, str(e))

    def _on_export_done(self, count):
        self._btn_export.config(state="normal", text="🚀  Send to DiamondFire")
        self._status(f"✓  Export complete — {count} function(s) sent!")
        messagebox.showinfo("Done", f"Successfully sent {count} function(s) to DiamondFire!\n"
                                    "Make sure the DF Code Client is running.")

    def _on_export_error(self, msg):
        self._btn_export.config(state="normal", text="🚀  Send to DiamondFire")
        self._status(f"✗  Export failed: {msg}")
        messagebox.showerror("Export Error",
                             f"Failed to send to DiamondFire:\n\n{msg}\n\n"
                             "Make sure the DF Code Client is running and connected.")

    def _status(self, msg):
        self._status_var.set(msg)


if __name__ == "__main__":
    app = NoiseMapApp()
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure("TScale",    background=SURFACE, troughcolor=PANEL, sliderlength=14)
    style.configure("TCombobox", fieldbackground=ENTRY_BG, background=ENTRY_BG,
                    foreground=TEXT, selectbackground=PANEL)
    app.mainloop()