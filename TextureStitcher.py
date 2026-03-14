import math, os, sys, threading, traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import pygame
    from pygame.locals import *
    from OpenGL.GL import *
    from OpenGL.GLU import *
    GL_OK = True
except Exception:
    GL_OK = False

if not PIL_OK:
    import tkinter.messagebox as _mb
    _mb.showerror("Missing dependency", "Run:  pip install Pillow numpy")
    sys.exit(1)

from PIL import Image, ImageTk


@dataclass
class Material:
    name: str
    texture_path: Optional[str] = None
    ka: str = "1.000 1.000 1.000"
    kd: str = "0.800 0.800 0.800"
    ks: str = "0.000 0.000 0.000"
    ns: str = "10.0"
    d:  str = "1.0"
    atlas_x: int = 0
    atlas_y: int = 0
    atlas_w: int = 0
    atlas_h: int = 0

@dataclass
class Face:
    material: str
    verts: list = field(default_factory=list)


def _resolve_texture(tex_str: str, search_dirs: list) -> Optional[str]:
    """
    Try to find a texture file, searching multiple directories.
    Handles absolute paths, relative paths, and bare filenames.
    Also tries common image extensions if the exact file isn't found.
    """
    candidates = [Path(tex_str)]
    for d in search_dirs:
        candidates.append(d / tex_str)
        candidates.append(d / Path(tex_str).name)
        stem = Path(tex_str).stem
        for ext in [".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tiff"]:
            candidates.append(d / (stem + ext))
    for c in candidates:
        try:
            if c.exists():
                return str(c.resolve())
        except Exception:
            pass
    return None


def parse_mtl(mtl_path: str, extra_textures: list) -> dict:
    mtl_path = Path(mtl_path).resolve()
    mtl_dir  = mtl_path.parent
    search_dirs = [mtl_dir, mtl_dir.parent, mtl_dir.parent.parent]
    materials, current = {}, None
    with open(mtl_path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            key   = parts[0].lower()
            if key == 'newmtl':
                current = Material(name=parts[1])
                materials[current.name] = current
            elif current is None:
                continue
            elif key == 'map_kd':
                tex_str = line[len(parts[0]):].strip()
                resolved = _resolve_texture(tex_str, search_dirs)
                current.texture_path = resolved
            elif key == 'ka':  current.ka = ' '.join(parts[1:])
            elif key == 'kd':  current.kd = ' '.join(parts[1:])
            elif key == 'ks':  current.ks = ' '.join(parts[1:])
            elif key == 'ns':  current.ns = parts[1]
            elif key in ('d', 'tr'): current.d = parts[1]
    for i, tex in enumerate(extra_textures):
        mat = list(materials.values())[i] if i < len(materials) else None
        if mat:
            mat.texture_path = str(Path(tex).resolve())
    return materials


def parse_obj(obj_path: str):
    """Returns (vertices, uvs, normals, faces) — all 1-based indices."""
    verts, uvs, norms, faces = [], [], [], []
    cur_mat = "__default__"
    with open(obj_path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            key   = parts[0].lower()
            if   key == 'v':      verts.append(tuple(float(x) for x in parts[1:4]))
            elif key == 'vt':     uvs.append(tuple(float(x) for x in parts[1:3]))
            elif key == 'vn':     norms.append(tuple(float(x) for x in parts[1:4]))
            elif key == 'usemtl': cur_mat = parts[1]
            elif key == 'f':
                face = Face(material=cur_mat)
                for tok in parts[1:]:
                    idx = tok.split('/')
                    vi  = int(idx[0])   if len(idx) > 0 and idx[0] else 0
                    vti = int(idx[1])   if len(idx) > 1 and idx[1] else 0
                    vni = int(idx[2])   if len(idx) > 2 and idx[2] else 0
                    face.verts.append((vi, vti, vni))
                if len(face.verts) > 3:
                    v0 = face.verts[0]
                    for i in range(1, len(face.verts) - 1):
                        faces.append(Face(face.material,
                                          [v0, face.verts[i], face.verts[i + 1]]))
                else:
                    faces.append(face)
    return verts, uvs, norms, faces


def _shelf_pack(scaled_imgs, atlas_size, padding):
    """Try to pack list of (name, img) into atlas_size. Returns placements or None."""
    placements = []
    cx, cy, row_h = 0, 0, 0
    for name, img in scaled_imgs:
        w, h = img.size
        if cx + w + padding > atlas_size:
            cx = 0; cy += row_h + padding; row_h = 0
        if cy + h > atlas_size:
            return None
        placements.append((name, cx, cy, w, h))
        cx += w + padding
        row_h = max(row_h, h)
    return placements


def pack_atlas(materials: dict, padding: int = 2, log=None) -> tuple:
    """
    Auto-sizes atlas to smallest power-of-2 square that fits all textures.
    Returns (atlas_image, atlas_size).
    """
    def _log(m, t=""): log(m, t) if log else None

    imgs = {}
    for name, mat in materials.items():
        p = mat.texture_path
        if p and Path(p).exists():
            imgs[name] = Image.open(p).convert("RGBA")
        else:
            if p:
                _log(f"  ⚠ not found: {p}  → using Kd colour", "warn")
            else:
                _log(f"  no map_Kd for '{name}'  → using Kd colour", "dim")
            try:
                rgb = tuple(int(float(x) * 255) for x in mat.kd.split())
            except Exception:
                rgb = (180, 180, 180)
            imgs[name] = Image.new("RGBA", (64, 64), (*rgb, 255))

    order = sorted(imgs.items(), key=lambda kv: kv[1].size[1], reverse=True)

    total_px = sum(img.size[0] * img.size[1] for _, img in order)
    min_side = max(64, 1 << math.ceil(math.log2(math.sqrt(total_px) * 1.15 + 1)))

    atlas_size = min_side
    while True:
        scaled = []
        for name, img in order:
            w, h = img.size
            if w > atlas_size:
                h = int(h * atlas_size / w); w = atlas_size
                img = img.resize((w, h), Image.LANCZOS)
            scaled.append((name, img))
        result = _shelf_pack(scaled, atlas_size, padding)
        if result is not None:
            break
        atlas_size *= 2

    _log(f"       Auto atlas size: {atlas_size}×{atlas_size}", "dim")

    atlas = Image.new("RGBA", (atlas_size, atlas_size), (0, 0, 0, 0))
    scaled_dict = dict(scaled)
    for name, x, y, w, h in result:
        atlas.paste(scaled_dict[name], (x, y))
        mat = materials[name]
        mat.atlas_x, mat.atlas_y, mat.atlas_w, mat.atlas_h = x, y, w, h

    used_h = max(y + h for _, x, y, w, h in result)
    used_h_p2 = 1 << math.ceil(math.log2(max(used_h, 1)))
    atlas = atlas.crop((0, 0, atlas_size, min(used_h_p2, atlas_size)))

    actual_h = atlas.size[1]
    return atlas, atlas_size, actual_h


def remap_uvs(orig_uvs: list, faces: list,
              materials: dict, atlas_w: int, atlas_h: int):
    """
    Returns (new_uvs, new_faces).

    Uses atlas_w for U and atlas_h for V so the cropped atlas dimensions
    are used correctly — previously dividing by a single atlas_size caused
    V to be wrong whenever the atlas was cropped shorter than it was wide.

    u % 1.0 maps 1.0 → 0.0 which is correct for tiling, but we clamp it
    to [0, 1) then nudge the upper edge inward by half a pixel to avoid
    sampling the black transparent border of the tile.
    """
    new_uvs   = list(orig_uvs)
    new_faces = []

    face_mats = set(f.material for f in faces)
    missing_mats = face_mats - set(materials.keys())
    if missing_mats:
        import sys
        print(f"WARNING: faces reference materials not in MTL: {missing_mats}", file=sys.stderr)

    for face in faces:
        mat = materials.get(face.material)
        new_verts = []
        for (vi, vti, vni) in face.verts:
            if vti == 0 or mat is None or mat.atlas_w == 0:
                new_verts.append((vi, vti, vni))
                continue

            u, v = orig_uvs[vti - 1]
            u = u % 1.0 if u != 1.0 else 1.0
            v = v % 1.0 if v != 1.0 else 1.0

            hp_u = 0.5 / mat.atlas_w
            hp_v = 0.5 / mat.atlas_h
            u = max(hp_u, min(1.0 - hp_u, u))
            v = max(hp_v, min(1.0 - hp_v, v))

            new_u = (mat.atlas_x + u * mat.atlas_w) / atlas_w
            new_v = 1.0 - (mat.atlas_y + (1.0 - v) * mat.atlas_h) / atlas_h

            new_idx = len(new_uvs) + 1
            new_uvs.append((new_u, new_v))
            new_verts.append((vi, new_idx, vni))

        new_faces.append(Face(face.material, new_verts))

    return new_uvs, new_faces


def write_mtl(path: str, atlas_tex_name: str, mat_name: str = "AtlasMaterial"):
    with open(path, 'w') as fh:
        fh.write("# OBJ Texture Stitcher output\n\n")
        fh.write(f"newmtl {mat_name}\n")
        fh.write("Ka 1.000 1.000 1.000\nKd 1.000 1.000 1.000\n")
        fh.write("Ks 0.000 0.000 0.000\nNs 10.0\nd 1.0\n")
        fh.write(f"map_Kd {atlas_tex_name}\n")


def write_obj(path: str, mtl_filename: str, verts, uvs, norms, faces,
              mat_name: str = "AtlasMaterial"):
    with open(path, 'w') as fh:
        fh.write("# OBJ Texture Stitcher output\n\n")
        fh.write(f"mtllib {mtl_filename}\n\n")
        for v in verts:
            fh.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        fh.write("\n")
        for uv in uvs:
            fh.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")
        fh.write("\n")
        for n in norms:
            fh.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
        fh.write("\n")
        fh.write(f"usemtl {mat_name}\n")
        for face in faces:
            tokens = []
            for vi, vti, vni in face.verts:
                if   vti and vni: tokens.append(f"{vi}/{vti}/{vni}")
                elif vti:         tokens.append(f"{vi}/{vti}")
                elif vni:         tokens.append(f"{vi}//{vni}")
                else:             tokens.append(str(vi))
            fh.write(f"f {' '.join(tokens)}\n")




def save_debug_atlas(atlas_img: Image.Image, new_uvs: list, new_faces: list,
                     atlas_w: int, atlas_h: int, out_path: str):
    """
    Saves a copy of the atlas with every face's UV centroid plotted as a
    coloured dot, so you can see exactly where each face is sampling.
    Red  = face has UVs outside [0,1] after remap (bad)
    Green = face centroid is inside atlas bounds (good)
    """
    from PIL import ImageDraw
    debug = atlas_img.copy().convert("RGB")
    draw  = ImageDraw.Draw(debug)

    for face in new_faces:
        us, vs = [], []
        for (vi, vti, vni) in face.verts:
            if vti == 0 or vti > len(new_uvs): continue
            u, v = new_uvs[vti - 1]
            us.append(u); vs.append(v)
        if not us: continue
        cu = sum(us) / len(us)
        cv = sum(vs) / len(vs)
        px = int(cu * atlas_w)
        py = int((1.0 - cv) * atlas_h)
        bad = not (0 <= px < atlas_w and 0 <= py < atlas_h)
        col = (255, 0, 0) if bad else (0, 255, 0)
        r = 2
        draw.ellipse([px-r, py-r, px+r, py+r], fill=col)

    debug.save(out_path)


def _load_gl_texture(path: str) -> int:
    """Upload a PIL image to a new GL texture and return its ID."""
    from OpenGL.GL import (glGenTextures, glBindTexture, glTexImage2D,
                            glTexParameteri, GL_TEXTURE_2D, GL_RGBA,
                            GL_UNSIGNED_BYTE, GL_TEXTURE_MIN_FILTER,
                            GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    img = Image.open(path).convert("RGBA").transpose(Image.FLIP_TOP_BOTTOM)
    tid = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height,
                 0, GL_RGBA, GL_UNSIGNED_BYTE, img.tobytes())
    return tid


def _run_viewer_in_process(obj_path: str, mtl_or_tex: str, title: str):
    """
    Entry point when launched as subprocess for 3D viewing.

    mtl_or_tex:
      - path ending in .mtl  → load all materials, bind per-face texture
      - any other path        → single texture applied to whole mesh
      - "NONE"                → no texture (white shaded)
    """
    import pygame
    from pygame.locals import DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_ESCAPE
    from pygame.locals import MOUSEBUTTONDOWN, MOUSEBUTTONUP, MOUSEMOTION
    from OpenGL.GL import (
        glClear, glClearColor, glEnable, glDisable,
        glBindTexture, glBegin, glEnd,
        glVertex3f, glTexCoord2f, glNormal3f, glColor3f,
        glTranslatef, glRotatef, glScalef, glLoadIdentity,
        glMatrixMode,
        GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_TEST, GL_TEXTURE_2D, GL_LIGHTING,
        GL_TRIANGLES, GL_MODELVIEW, GL_PROJECTION,
    )
    from OpenGL.GLU import gluPerspective

    verts, uvs, norms, faces = parse_obj(obj_path)
    if not verts:
        print("No geometry found."); return

    xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
    mcx = (min(xs)+max(xs))/2; mcy = (min(ys)+max(ys))/2; mcz = (min(zs)+max(zs))/2
    span  = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)) or 1.0
    mscale = 2.0 / span

    pygame.init()
    W, H = 900, 650
    pygame.display.set_mode((W, H), DOUBLEBUF | OPENGL)
    pygame.display.set_caption(title)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glDisable(GL_LIGHTING)
    glClearColor(0.12, 0.12, 0.16, 1)

    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(45, W/H, 0.01, 500)
    glMatrixMode(GL_MODELVIEW)

    mat_tex_ids: dict = {}
    fallback_tex_id = None

    if mtl_or_tex != "NONE" and Path(mtl_or_tex).exists():
        if mtl_or_tex.lower().endswith(".mtl"):
            try:
                mats = parse_mtl(mtl_or_tex, [])
                for name, mat in mats.items():
                    if mat.texture_path and Path(mat.texture_path).exists():
                        mat_tex_ids[name] = _load_gl_texture(mat.texture_path)
                    else:
                        mat_tex_ids[name] = None
            except Exception as e:
                print(f"MTL load error: {e}")
        else:
            fallback_tex_id = _load_gl_texture(mtl_or_tex)

    def _bind_for_face(mat_name: str):
        tid = mat_tex_ids.get(mat_name, fallback_tex_id)
        if tid is not None:
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, tid)
        else:
            glDisable(GL_TEXTURE_2D)

    rot_x, rot_y = 20.0, -30.0
    zoom = -4.0
    drag = False
    last = (0, 0)
    clock = pygame.time.Clock()

    def draw():
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glColor3f(1.0, 1.0, 1.0)
        glLoadIdentity()
        glTranslatef(0, 0, zoom)
        glRotatef(rot_x, 1, 0, 0)
        glRotatef(rot_y, 0, 1, 0)
        glScalef(mscale, mscale, mscale)
        glTranslatef(-mcx, -mcy, -mcz)

        cur_mat = None
        glBegin(GL_TRIANGLES)
        for face in faces:
            if face.material != cur_mat:
                glEnd()
                _bind_for_face(face.material)
                cur_mat = face.material
                glBegin(GL_TRIANGLES)
            for (vi, vti, vni) in face.verts:
                if vni and norms: glNormal3f(*norms[vni-1])
                if vti and uvs:   glTexCoord2f(*uvs[vti-1])
                glVertex3f(*verts[vi-1])
        glEnd()
        pygame.display.flip()

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == QUIT:                              running = False
            elif ev.type == KEYDOWN and ev.key == K_ESCAPE: running = False
            elif ev.type == MOUSEBUTTONDOWN:
                if ev.button == 1: drag = True; last = ev.pos
                if ev.button == 4: zoom = min(zoom + 0.3, -0.3)
                if ev.button == 5: zoom = max(zoom - 0.3, -60)
            elif ev.type == MOUSEBUTTONUP:
                if ev.button == 1: drag = False
            elif ev.type == MOUSEMOTION and drag:
                dx = ev.pos[0] - last[0]; dy = ev.pos[1] - last[1]
                rot_y += dx * 0.5; rot_x += dy * 0.5
                last = ev.pos
        draw()
        clock.tick(60)
    pygame.quit()


def launch_viewer(obj_path: str, mtl_or_tex: Optional[str], title: str = "3D Viewer"):
    """
    Spawn viewer subprocess.  mtl_or_tex can be:
      - a .mtl file path  (before-viewer: loads per-material textures)
      - a .png/.jpg path  (after-viewer: single atlas)
      - None / missing    (no texture)
    """
    if not GL_OK:
        messagebox.showwarning("3D Viewer",
            "pygame / PyOpenGL not installed.\n"
            "Run:  pip install PyOpenGL PyOpenGL_accelerate pygame")
        return
    import subprocess
    arg = mtl_or_tex if (mtl_or_tex and Path(mtl_or_tex).exists()) else "NONE"
    subprocess.Popen(
        [sys.executable, __file__, "--viewer", obj_path, arg, title],
        close_fds=True
    )


BG      = "#10111a"
SURFACE = "#181926"
CARD    = "#1e2030"
BORDER  = "#2d2f45"
ACCENT  = "#7c6af7"
ACCENT2 = "#a78bfa"
TEXT    = "#cdd6f4"
MUTED   = "#585b78"
SUCCESS = "#a6e3a1"
ERROR   = "#f38ba8"
WARNING = "#f9e2af"
TEAL    = "#89dceb"

FH  = ("Segoe UI", 20, "bold")
FL  = ("Consolas", 9,  "bold")
FM  = ("Consolas", 9)
FB  = ("Consolas", 10, "bold")
FLG = ("Consolas", 8)


def _style_ttk():
    s = ttk.Style()
    try: s.theme_use("clam")
    except: pass
    s.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE,
                foreground=TEXT, selectbackground=SURFACE, selectforeground=TEXT,
                bordercolor=BORDER, arrowcolor=ACCENT2)
    s.configure("Atlas.Horizontal.TProgressbar",
                troughcolor=SURFACE, background=ACCENT,
                bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)


class Divider(tk.Frame):
    def __init__(self, parent, label="", **kw):
        super().__init__(parent, bg=BG, **kw)
        if label:
            tk.Label(self, text=label, fg=ACCENT2, bg=BG, font=FL).pack(side="left")
        tk.Frame(self, bg=BORDER, height=1).pack(side="left", fill="x",
                                                  expand=True, padx=(6, 0))


class FilePicker(tk.Frame):
    def __init__(self, parent, label, mode="open", filetypes=None,
                 default="", lwidth=14, **kw):
        super().__init__(parent, bg=BG, **kw)
        self.mode      = mode
        self.filetypes = filetypes or [("All", "*.*")]
        self.var       = tk.StringVar(value=default)
        tk.Label(self, text=label, fg=MUTED, bg=BG, font=FL,
                 width=lwidth, anchor="w").pack(side="left")
        e = tk.Entry(self, textvariable=self.var, bg=SURFACE, fg=TEXT,
                     insertbackground=ACCENT, relief="flat", font=FM, bd=0,
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT)
        e.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 6))
        tk.Button(self, text="…", command=self._browse, bg=CARD, fg=ACCENT2,
                  activebackground=BORDER, activeforeground=TEXT,
                  font=FB, relief="flat", bd=0, cursor="hand2",
                  padx=10, pady=3).pack(side="left")

    def _browse(self):
        p = ""
        if   self.mode == "open": p = filedialog.askopenfilename(filetypes=self.filetypes)
        elif self.mode == "save": p = filedialog.asksaveasfilename(filetypes=self.filetypes)
        elif self.mode == "dir":  p = filedialog.askdirectory()
        if p: self.var.set(p)

    def get(self): return self.var.get().strip()
    def set(self, v): self.var.set(v)


class TextureList(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._paths = []
        hdr = tk.Frame(self, bg=BG); hdr.pack(fill="x", pady=(0, 4))
        tk.Label(hdr, text="TEXTURE OVERRIDES", fg=MUTED, bg=BG, font=FL).pack(side="left")
        tk.Label(hdr, text="  optional — overrides map_Kd order",
                 fg=MUTED, bg=BG, font=("Consolas", 8)).pack(side="left")
        btn = tk.Frame(self, bg=BG); btn.pack(fill="x", pady=(0, 4))
        for lbl, cmd in [("＋ Add", self._add), ("↑", self._up),
                          ("↓", self._dn), ("✕", self._rm)]:
            tk.Button(btn, text=lbl, command=cmd, bg=CARD, fg=ACCENT2,
                      activebackground=BORDER, activeforeground=TEXT,
                      font=FB, relief="flat", bd=0, cursor="hand2",
                      padx=8, pady=2).pack(side="left", padx=(0, 5))
        frm = tk.Frame(self, bg=BORDER); frm.pack(fill="both", expand=True)
        self._lb = tk.Listbox(frm, bg=SURFACE, fg=TEXT, selectbackground=ACCENT,
                              selectforeground="white", font=FM, relief="flat",
                              bd=0, highlightthickness=0, activestyle="none", height=4)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self._lb.yview)
        self._lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._lb.pack(fill="both", expand=True)

    def _add(self):
        ps = filedialog.askopenfilenames(title="Select textures",
             filetypes=[("Images", "*.png *.jpg *.jpeg *.tga *.bmp *.tiff"),
                        ("All", "*.*")])
        for p in ps:
            self._paths.append(p); self._lb.insert("end", f"  {Path(p).name}")

    def _sel(self):
        s = self._lb.curselection(); return s[0] if s else None

    def _up(self):
        i = self._sel()
        if i is None or i == 0: return
        self._paths[i-1], self._paths[i] = self._paths[i], self._paths[i-1]
        t = self._lb.get(i); self._lb.delete(i); self._lb.insert(i-1, t)
        self._lb.selection_set(i-1)

    def _dn(self):
        i = self._sel()
        if i is None or i >= len(self._paths)-1: return
        self._paths[i], self._paths[i+1] = self._paths[i+1], self._paths[i]
        t = self._lb.get(i); self._lb.delete(i); self._lb.insert(i+1, t)
        self._lb.selection_set(i+1)

    def _rm(self):
        i = self._sel()
        if i is None: return
        del self._paths[i]; self._lb.delete(i)

    def get(self): return list(self._paths)


class LogPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        frm = tk.Frame(self, bg=BORDER); frm.pack(fill="both", expand=True)
        self._t = tk.Text(frm, bg="#0d0e18", fg=TEXT, font=FLG, relief="flat",
                          bd=0, highlightthickness=0, state="disabled",
                          wrap="word", height=9)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self._t.yview)
        self._t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._t.pack(fill="both", expand=True, padx=1, pady=1)
        for tag, fg in [("ok", SUCCESS), ("err", ERROR), ("warn", WARNING),
                         ("acc", ACCENT2), ("dim", MUTED), ("teal", TEAL)]:
            self._t.tag_config(tag, foreground=fg)

    def log(self, msg, tag=""):
        self._t.configure(state="normal")
        self._t.insert("end", msg + "\n", tag)
        self._t.see("end")
        self._t.configure(state="disabled")

    def clear(self):
        self._t.configure(state="normal")
        self._t.delete("1.0", "end")
        self._t.configure(state="disabled")


class AtlasThumb(tk.Frame):
    SIZE = 220
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._cv = tk.Canvas(self, bg=CARD, highlightthickness=1,
                             highlightbackground=BORDER,
                             width=self.SIZE, height=self.SIZE)
        self._cv.pack()
        self._ref = None
        self._cv.create_text(self.SIZE//2, self.SIZE//2,
                             text="no preview", fill=MUTED, font=FM)

    def show(self, pil_img):
        self._cv.delete("all")
        t = pil_img.copy().convert("RGBA")
        t.thumbnail((self.SIZE - 4, self.SIZE - 4), Image.LANCZOS)
        self._ref = ImageTk.PhotoImage(t)
        x = (self.SIZE - t.width)  // 2
        y = (self.SIZE - t.height) // 2
        self._cv.create_image(x, y, anchor="nw", image=self._ref)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OBJ Texture Stitcher")
        self.configure(bg=BG)
        self.minsize(960, 700)
        _style_ttk()
        self._build()
        self.update_idletasks()
        w, h = 1080, 820
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        bar = tk.Frame(self, bg=BG); bar.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(bar, text="OBJ Texture Stitcher", fg=TEXT, bg=BG, font=FH).pack(side="left")
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x", padx=24, pady=(10, 0))

        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True, padx=24, pady=14)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)

        left  = tk.Frame(root, bg=BG); left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(8, weight=1)

        right = tk.Frame(root, bg=BG); right.grid(row=0, column=1, sticky="n")

        Divider(left, "INPUT").grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self._obj = FilePicker(left, "OBJ FILE",
            filetypes=[("OBJ", "*.obj"), ("All", "*.*")])
        self._obj.grid(row=1, column=0, sticky="ew", pady=2)
        self._obj.var.trace_add("write", lambda *_: self._auto_mtl())

        self._mtl = FilePicker(left, "MTL FILE",
            filetypes=[("MTL", "*.mtl"), ("All", "*.*")])
        self._mtl.grid(row=2, column=0, sticky="ew", pady=2)

        self._texlist = TextureList(left)
        self._texlist.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        Divider(left, "OUTPUT").grid(row=4, column=0, sticky="ew", pady=(18, 6))

        self._outdir = FilePicker(left, "OUTPUT FOLDER", mode="dir",
                                   default=str(Path.home() / 'Desktop'))
        self._outdir.grid(row=5, column=0, sticky="ew", pady=2)

        bn_row = tk.Frame(left, bg=BG); bn_row.grid(row=6, column=0, sticky="ew", pady=(6, 2))
        tk.Label(bn_row, text="BASE NAME", fg=MUTED, bg=BG, font=FL,
                 width=14, anchor="w").pack(side="left")
        self._basename = tk.Entry(bn_row, bg=SURFACE, fg=TEXT,
                                   insertbackground=ACCENT, relief="flat",
                                   font=FM, bd=0, highlightthickness=1,
                                   highlightbackground=BORDER, highlightcolor=ACCENT)
        self._basename.insert(0, "output")
        self._basename.pack(side="left", fill="x", expand=True, ipady=5)
        tk.Label(bn_row, text="  → .obj / .mtl / _atlas.png",
                 fg=MUTED, bg=BG, font=("Consolas", 8)).pack(side="left", padx=(8, 0))

        opts = tk.Frame(left, bg=BG); opts.grid(row=7, column=0, sticky="ew", pady=(12, 0))

        def _lbl(t): tk.Label(opts, text=t, fg=MUTED, bg=BG, font=FL).pack(side="left")

        _lbl("PADDING")
        self._padding = tk.Spinbox(opts, from_=0, to=64, width=4, font=FM,
                                    bg=SURFACE, fg=TEXT, buttonbackground=CARD,
                                    relief="flat", highlightthickness=1,
                                    highlightbackground=BORDER, insertbackground=ACCENT)
        self._padding.delete(0, "end"); self._padding.insert(0, "2")
        self._padding.pack(side="left", ipady=4, padx=(4, 16))

        _lbl("MAT NAME")
        self._matname = tk.Entry(opts, bg=SURFACE, fg=TEXT, font=FM, width=16,
                                  relief="flat", highlightthickness=1,
                                  highlightbackground=BORDER, insertbackground=ACCENT)
        self._matname.insert(0, "AtlasMaterial")
        self._matname.pack(side="left", ipady=4, padx=(4, 0))

        bright_row = tk.Frame(left, bg=BG); bright_row.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        tk.Label(bright_row, text="BRIGHTNESS", fg=MUTED, bg=BG, font=FL,
                 width=14, anchor="w").pack(side="left")
        self._brightness = tk.DoubleVar(value=1.0)
        self._bright_slider = tk.Scale(
            bright_row, variable=self._brightness,
            from_=0.5, to=3.0, resolution=0.05, orient="horizontal",
            bg=BG, fg=TEXT, troughcolor=SURFACE, highlightthickness=0,
            activebackground=ACCENT, sliderrelief="flat", bd=0,
            length=200, showvalue=False, command=lambda _: self._update_bright_label()
        )
        self._bright_slider.pack(side="left", padx=(4, 6))
        self._bright_label = tk.Label(bright_row, text="1.00×", fg=ACCENT2, bg=BG, font=FL, width=5)
        self._bright_label.pack(side="left")
        tk.Label(bright_row, text="  boost for MC text-display mesher (canvas gamma fix)",
                 fg=MUTED, bg=BG, font=("Consolas", 8)).pack(side="left", padx=(4, 0))

        Divider(left, "LOG").grid(row=9, column=0, sticky="ew", pady=(16, 4))
        self._log = LogPanel(left)
        self._log.grid(row=10, column=0, sticky="nsew")

        pf = tk.Frame(left, bg=BG); pf.grid(row=11, column=0, sticky="ew", pady=(8, 0))
        self._pbar = ttk.Progressbar(pf, style="Atlas.Horizontal.TProgressbar",
                                      mode="determinate")
        self._pbar.pack(fill="x")
        self._status = tk.StringVar(value="Ready.")
        tk.Label(pf, textvariable=self._status, fg=MUTED, bg=BG,
                 font=FM).pack(anchor="w", pady=(3, 0))

        bf = tk.Frame(left, bg=BG); bf.grid(row=12, column=0, sticky="ew", pady=(10, 6))
        self._run_btn = tk.Button(bf, text="STITCH ATLAS  →",
                                   command=self._run,
                                   bg=ACCENT, fg="white", activebackground=ACCENT2,
                                   activeforeground="white",
                                   font=("Consolas", 11, "bold"),
                                   relief="flat", bd=0, cursor="hand2",
                                   padx=24, pady=9)
        self._run_btn.pack(side="right")
        tk.Button(bf, text="CLEAR LOG", command=self._log.clear,
                  bg=CARD, fg=MUTED, activebackground=BORDER, activeforeground=TEXT,
                  font=FB, relief="flat", bd=0, cursor="hand2",
                  padx=14, pady=9).pack(side="right", padx=(0, 8))

        Divider(right, "ATLAS PREVIEW").pack(fill="x", pady=(0, 6))
        self._thumb = AtlasThumb(right)
        self._thumb.pack(pady=(0, 16))

        Divider(right, "3D VIEWER").pack(fill="x", pady=(0, 8))

        self._btn_before = tk.Button(right, text="▶  VIEW ORIGINAL",
                                      command=self._view_before,
                                      bg=CARD, fg=TEAL, activebackground=BORDER,
                                      activeforeground=TEXT, font=FB, relief="flat",
                                      bd=0, cursor="hand2", padx=12, pady=8)
        self._btn_before.pack(fill="x", pady=(0, 5))

        self._btn_after = tk.Button(right, text="▶  VIEW STITCHED",
                                     command=self._view_after,
                                     bg=CARD, fg=SUCCESS, activebackground=BORDER,
                                     activeforeground=TEXT, font=FB, relief="flat",
                                     bd=0, cursor="hand2", padx=12, pady=8,
                                     state="disabled")
        self._btn_after.pack(fill="x")

        if not GL_OK:
            tk.Label(right, text="⚠  Install PyOpenGL + pygame\nfor 3D viewer",
                     fg=WARNING, bg=BG, font=("Consolas", 8),
                     justify="center").pack(pady=(8, 0))

        tk.Label(right,
                 text="\nDrag  →  rotate\nScroll  →  zoom\nEsc  →  close",
                 fg=MUTED, bg=BG, font=("Consolas", 8),
                 justify="left").pack(anchor="w", pady=(10, 0))

    def _update_bright_label(self):
        self._bright_label.config(text=f"{self._brightness.get():.2f}×")

    def _auto_mtl(self):
        p = self._obj.get()
        if p:
            m = Path(p).with_suffix(".mtl")
            if m.exists() and not self._mtl.get():
                self._mtl.set(str(m))

    def _out_paths(self):
        d    = Path(self._outdir.get() or ".")
        base = self._basename.get().strip() or "output"
        return (str(d / f"{base}.obj"),
                str(d / f"{base}.mtl"),
                str(d / f"{base}_atlas.png"))

    def _view_before(self):
        obj = self._obj.get()
        if not obj or not Path(obj).exists():
            messagebox.showwarning("Viewer", "Select a valid OBJ first."); return
        mtl = self._mtl.get()
        mtl_arg = mtl if (mtl and Path(mtl).exists()) else None
        launch_viewer(obj, mtl_arg, "Before — Original")

    def _view_after(self):
        out_obj, _, out_tex = self._out_paths()
        if not Path(out_obj).exists():
            messagebox.showwarning("Viewer", "Run Stitch first."); return
        launch_viewer(out_obj, out_tex, "After — Stitched Atlas")

    def _run(self):
        obj = self._obj.get(); mtl = self._mtl.get()
        if not obj or not Path(obj).exists():
            messagebox.showerror("Error", "Select a valid OBJ file."); return
        if not mtl or not Path(mtl).exists():
            messagebox.showerror("Error", "Select a valid MTL file."); return
        out_obj, out_mtl, out_tex = self._out_paths()
        try:
            Path(out_obj).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot write to output folder:\n{e}"); return

        self._run_btn.configure(state="disabled", text="STITCHING…")
        self._btn_after.configure(state="disabled")
        self._log.clear(); self._pbar["value"] = 0

        threading.Thread(target=self._do_stitch, daemon=True, kwargs=dict(
            obj_path=obj, mtl_path=mtl,
            textures=self._texlist.get(),
            out_obj=out_obj, out_mtl=out_mtl, out_tex=out_tex,
            padding=int(self._padding.get()),
            mat_name=self._matname.get().strip() or "AtlasMaterial",
            brightness=float(self._brightness.get()),
        )).start()

    def _do_stitch(self, obj_path, mtl_path, textures,
                   out_obj, out_mtl, out_tex,
                   padding, mat_name, brightness=1.0):

        def log(m, t=""): self.after(0, self._log.log, m, t)
        def prog(v, s):
            self.after(0, lambda: self._pbar.__setitem__("value", v))
            self.after(0, self._status.set, s)

        try:
            log("━" * 54, "dim")
            log("  OBJ Texture Stitcher", "acc")
            log("━" * 54, "dim")

            prog(5, "Parsing MTL…")
            log(f"\n[1/5]  MTL  {Path(mtl_path).name}")
            materials = parse_mtl(mtl_path, textures)
            for name, mat in materials.items():
                if mat.texture_path and Path(mat.texture_path).exists():
                    tp = Path(mat.texture_path).name
                    tag = "dim"
                else:
                    tp = f"MISSING ⚠  ({mat.texture_path or 'no map_Kd in MTL'})"
                    tag = "warn"
                log(f"       {name:24s}  →  {tp}", tag)

            prog(20, "Parsing OBJ…")
            log(f"\n[2/5]  OBJ  {Path(obj_path).name}")
            verts, uvs, norms, faces = parse_obj(obj_path)
            log(f"       {len(verts)} verts  {len(uvs)} UVs  "
                f"{len(norms)} normals  {len(faces)} tris", "ok")
            face_mat_names = sorted(set(f.material for f in faces))
            log(f"       Materials used in faces: {face_mat_names}", "dim")

            prog(40, "Packing atlas…")
            log(f"\n[3/5]  Atlas  pad={padding} (auto-sizing)")
            atlas_img, atlas_size, atlas_h = pack_atlas(materials, padding, log=log)
            self.after(0, self._thumb.show, atlas_img)
            for mname, mmat in materials.items():
                status = f"{mmat.atlas_w}×{mmat.atlas_h} @ ({mmat.atlas_x},{mmat.atlas_y})" if mmat.atlas_w else "NOT PLACED ⚠"
                log(f"       {mname:24s}  {status}", "warn" if not mmat.atlas_w else "dim")
            log(f"       Packed {len(materials)} texture(s)  →  {atlas_size}×{atlas_h}", "ok")

            prog(62, "Remapping UVs…")
            log(f"\n[4/5]  Remapping UVs (per-face duplication)")
            new_uvs, new_faces = remap_uvs(uvs, faces, materials, atlas_size, atlas_h)
            log(f"       {len(uvs)} → {len(new_uvs)} UV entries", "ok")

            prog(82, "Writing files…")
            log(f"\n[5/5]  Writing output")
            from PIL import ImageEnhance
            bg = Image.new('RGB', atlas_img.size, (0, 0, 0))
            bg.paste(atlas_img, mask=atlas_img.split()[3])
            if brightness != 1.0:
                bg = ImageEnhance.Brightness(bg).enhance(brightness)
                log(f"       Brightness: {brightness:.2f}×", "dim")
            bg.save(out_tex)
            log(f"       {out_tex}", "teal")
            write_mtl(out_mtl, Path(out_tex).name, mat_name)
            log(f"       {out_mtl}", "teal")
            write_obj(out_obj, Path(out_mtl).name,
                      verts, new_uvs, norms, new_faces, mat_name)
            log(f"       {out_obj}", "teal")

            debug_path = str(Path(out_tex).with_name(Path(out_tex).stem + "_debug.png"))
            save_debug_atlas(atlas_img, new_uvs, new_faces, atlas_size, atlas_h, debug_path)
            log(f"       debug UV map → {debug_path}", "dim")

            prog(100, "Done ✓")
            log("\n" + "━" * 54, "dim")
            log("  ✓  Stitching complete!", "ok")
            log("━" * 54, "dim")

            self.after(0, self._btn_after.configure, {"state": "normal"})
            self.after(0, messagebox.showinfo, "Done!",
                       f"Stitching complete!\n\n"
                       f"OBJ   →  {out_obj}\n"
                       f"MTL   →  {out_mtl}\n"
                       f"Atlas →  {out_tex}")

        except Exception:
            tb = traceback.format_exc()
            log(f"\n✕ ERROR\n{tb}", "err")
            prog(0, "Error — see log")
            self.after(0, messagebox.showerror, "Error", tb)

        finally:
            self.after(0, self._run_btn.configure,
                       {"state": "normal", "text": "STITCH ATLAS  →"})


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--viewer":
        obj_path    = sys.argv[2]
        mtl_or_tex  = sys.argv[3]
        title       = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else "3D Viewer"
        _run_viewer_in_process(obj_path, mtl_or_tex, title)
    else:
        app = App()
        app.mainloop()