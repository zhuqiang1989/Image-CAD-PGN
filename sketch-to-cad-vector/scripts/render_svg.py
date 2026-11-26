#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""render_svg.py — 手绘转 CAD 线稿的本地出图器（无外部依赖）

用途：把一个「受限子集」的 SVG（只含 line/polyline/polygon/rect/path(M L Z A)/text，
group 继承 stroke/stroke-width/stroke-dasharray）用 Pillow 直接光栅化为高分辨率 PNG。
这样 CAD 线稿完全由代码几何决定：可迭代、可复现、文字不会画错，不依赖生图模型。

用法：
    python render_svg.py <in.svg> <out.png> [--scale 2] [--preview out_preview.png]

支持的 SVG 子集（本技能自产 SVG 只用这些）：
    <svg width height viewBox>  <g fill stroke stroke-width stroke-dasharray>
    <line x1 y1 x2 y2> <polyline points fill> <polygon points> <rect x y w h rx>
    <path d="M x y L x y ... A rx ry rot laf sf x y ... Z"> <text x y font-size text-anchor>
"""
import argparse
import math
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simfang.ttf",
]
FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([0-9.]+)")
TOKEN_RE = re.compile(r"([A-Za-z])([^A-Za-z]*)")
NUMS = r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?"


def qname(tag):
    return tag.split("}", 1)[-1]


def pt(s):
    nums = re.findall(NUMS, s)
    return [float(n) for n in nums]


def color_of(v):
    if not v:
        return None
    v = v.strip().lower()
    named = {"none": None, "black": (0, 0, 0, 255), "white": (255, 255, 255, 255)}
    if v in named:
        return named[v]
    m = re.match(r"#([0-9a-f]{3}|[0-9a-f]{6})$", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return (r, g, b, 255)
    return (0, 0, 0, 255)


def style_of(el, parent):
    """合并 group 继承样式与元素自身 style="" 覆盖。"""
    st = dict(parent or {})
    raw = el.get("style") or ""
    for chunk in raw.split(";"):
        if ":" in chunk:
            k, v = chunk.split(":", 1)
            st[k.strip()] = v.strip()
    for key in ("fill", "stroke", "stroke-width", "stroke-dasharray", "font-size", "text-anchor"):
        if el.get(key) is not None:
            st[key] = el.get(key)
    if "stroke-width" in st:
        st["stroke-width"] = float(st["stroke-width"])
    dash = st.get("stroke-dasharray")
    if dash and dash.strip().lower() not in ("none", ""):
        st["dash"] = [max(0.1, float(v)) for v in pt(dash)]
    else:
        st.pop("dash", None)
    fs = st.get("font-size")
    if fs is None:
        m = FONT_SIZE_RE.search(raw)
        if m:
            fs = m.group(1)
    st["font-size"] = float(fs) if fs not in (None, "") else 16.0
    return st


def dash_poly(draw, pts, w, fill, dash, close=False):
    """沿折线按虚线段画（点划线、虚线用）。"""
    if len(pts) < 2:
        return
    segs = list(zip(pts, pts[1:]))
    if close:
        segs.append((pts[-1], pts[0]))
    i = 0
    on = True
    need = dash[0] if dash else 0.0
    di = 0
    for (x1, y1), (x2, y2) in segs:
        total = math.hypot(x2 - x1, y2 - y1)
        if total == 0:
            continue
        ux, uy = (x2 - x1) / total, (y2 - y1) / total
        travelled = 0.0
        while travelled < total:
            room = total - travelled
            if on:
                take = min(need, room)
                if take > 0.01:
                    draw.line([(x1 + ux * travelled, y1 + uy * travelled),
                               (x1 + ux * (travelled + take), y1 + uy * (travelled + take))],
                              fill=fill, width=max(1, int(round(w))), joint="curve")
                travelled += take
                need -= take
                if need <= 1e-6:
                    on = False
                    di = (di + 1) % len(dash)
                    need = dash[di]
            else:
                skip = min(need, room)
                travelled += skip
                need -= skip
                if need <= 1e-6:
                    on = True
                    di = (di + 1) % len(dash)
                    need = dash[di]
        # 段边界处重置相位，保证每条线开头都是实线段
        on, di, need = True, 0, dash[0]


def arc_pts(x0, y0, rx, ry, rot_deg, laf, sf, x1, y1):
    """SVG A 命令 -> 采样点列（端点法椭圆弧）。"""
    rx, ry = abs(float(rx)), abs(float(ry))
    if rx == 0 or ry == 0:
        return [(x1, y1)]
    phi = math.radians(rot_deg)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x0 - x1) / 2.0, (y0 - y1) / 2.0
    x1p = cp * dx + sp * dy
    y1p = -sp * dx + cp * dy
    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:  # 半径过小则放大到刚好过两点
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    sign = -1 if (bool(laf) != bool(sf)) else 1
    num = max(0.0, rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p)
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = sign * math.sqrt(num / den) if den else 0.0
    cxp = co * rx * y1p / ry
    cyp = -co * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x0 + x1) / 2.0
    cy = sp * cxp + cp * cyp + (y0 + y1) / 2.0

    def ang(ux, uy):
        a = math.atan2(uy, ux)
        return a if a >= 0 else a + 2 * math.pi

    th1 = ang((x1p - cxp) / rx, (y1p - cyp) / ry)
    th2 = ang((-x1p - cxp) / rx, (-y1p - cyp) / ry)
    dth = th2 - th1
    if sf and dth <= 0:
        dth += 2 * math.pi
    elif not sf and dth >= 0:
        dth -= 2 * math.pi
    n = max(2, int(abs(dth) / 0.012))
    out = []
    for k in range(n + 1):
        t = th1 + dth * k / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    return out


def path_segments(d):
    """解析 M/m L/l H/h V/v A/a Z/z -> 子路径点列（弧线已采样）。"""
    subs, cur = [], []
    pen, start = (0.0, 0.0), (0.0, 0.0)
    tokens = [(m.group(1), pt(m.group(2))) for m in TOKEN_RE.finditer(d)]

    def flush():
        nonlocal cur
        if len(cur) > 1:
            subs.append(cur)
        cur = []

    i = 0
    while i < len(tokens):
        cmd, vals = tokens[i]
        i += 1
        c, rel = cmd.upper(), cmd.islower()
        k = 0
        n = len(vals)
        if c in ("M", "L"):
            while k + 1 < n + 1 and k + 1 <= n:
                x, y = vals[k] + (pen[0] if rel else 0), vals[k + 1] + (pen[1] if rel else 0)
                k += 2
                if c == "M":
                    flush()
                    cur = [(x, y)]
                    start = (x, y)
                else:
                    cur.append((x, y))
                pen = (x, y)
        elif c in ("H", "V"):
            for v in vals:
                if c == "H":
                    pen = (v + (pen[0] if rel else 0), pen[1])
                else:
                    pen = (pen[0], v + (pen[1] if rel else 0))
                cur.append(pen)
        elif c == "A":
            while k + 7 <= n:
                rx, ry, rot, laf, sf, x, y = vals[k:k + 7]
                k += 7
                if rel:
                    x, y = x + pen[0], y + pen[1]
                cur.extend(arc_pts(pen[0], pen[1], rx, ry, rot, laf, sf, x, y))
                pen = (x, y)
        elif c in ("Q", "T"):
            while k + 1 < n + 1 and k + 1 <= n:
                cx, cy = vals[k] + (pen[0] if rel else 0), vals[k + 1] + (pen[1] if rel else 0)
                k += 2
                x, y = vals[k] + (pen[0] if rel else 0), vals[k + 1] + (pen[1] if rel else 0)
                k += 2
                for t in [i2 / 24 for i2 in range(1, 25)]:
                    a = (1 - t) ** 2 * pen[0] + 2 * (1 - t) * t * cx + t * t * x
                    b = (1 - t) ** 2 * pen[1] + 2 * (1 - t) * t * cy + t * t * y
                    cur.append((a, b))
                pen = (x, y)
        elif c == "Z":
            if len(cur) > 1:
                cur.append(start)
            flush()
            pen = start
    flush()
    return subs


def load_font(px):
    size = max(6, int(round(px)))
    for f in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def render(svg_path, out_path, scale=2.0, preview=None):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    vb = pt(root.get("viewBox") or "")
    w = float(root.get("width") or vb[2])
    h = float(root.get("height") or vb[3])
    if not vb:
        vb = [0, 0, w, h]
    img = Image.new("RGBA", (int(round(w * scale)), int(round(h * scale))), (255, 255, 255, 255))
    dr = ImageDraw.Draw(img)

    def walk(el, inherit):
        st = style_of(el, inherit)
        tag = qname(el.tag)
        col = color_of(st.get("stroke")) or (0, 0, 0, 255)
        fill = color_of(st.get("fill"))
        sw = float(st.get("stroke-width", 1.0)) * scale
        dash = [d * scale for d in st.get("dash", [])]
        if tag == "rect":
            x, y = (float(el.get("x", 0))) * scale, (float(el.get("y", 0))) * scale
            rw, rh = float(el.get("width", 0)) * scale, float(el.get("height", 0)) * scale
            box = [x, y, x + rw, y + rh]
            if fill:
                dr.rectangle(box, fill=fill)
            if el.get("stroke", inherit.get("stroke")) not in (None, "none"):
                dr.rectangle(box, outline=col, width=max(1, int(round(sw))))
        elif tag == "line":
            p = [(float(el.get(k, 0))) * scale for k in ("x1", "y1", "x2", "y2")]
            if dash:
                dash_poly(dr, [(p[0], p[1]), (p[2], p[3])], sw, col, dash)
            else:
                dr.line([(p[0], p[1]), (p[2], p[3])], fill=col, width=max(1, int(round(sw))))
        elif tag in ("polyline", "polygon"):
            raw = pt(el.get("points", ""))
            pts = [(raw[i] * scale, raw[i + 1] * scale) for i in range(0, len(raw) - 1, 2)]
            close = tag == "polygon" or (el.get("stroke") or "").lower() != "none"
            if fill:
                dr.polygon(pts, fill=fill)
            if dash:
                dash_poly(dr, pts, sw, col, dash, close=(tag == "polygon"))
            else:
                dr.line(pts, fill=col, width=max(1, int(round(sw))), joint="curve")
        elif tag == "path":
            for sub in path_segments(el.get("d", "")):
                pts = [(x * scale, y * scale) for x, y in sub]
                if len(pts) < 2:
                    continue
                closed = len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < 0.5 and abs(pts[0][1] - pts[-1][1]) < 0.5
                if fill:
                    dr.polygon(pts, fill=fill)
                if dash:
                    dash_poly(dr, pts, sw, col, dash, close=closed)
                else:
                    dr.line(pts, fill=col, width=max(1, int(round(sw))), joint="curve")
        elif tag == "text":
            txt = "".join(el.itertext()).strip()
            if txt:
                fpx = float(st["font-size"]) * scale
                font = load_font(fpx)
                tcol = color_of(el.get("fill")) or color_of(inherit.get("fill")) or (0, 0, 0, 255)
                x = float(el.get("x", 0)) * scale
                y = float(el.get("y", 0)) * scale
                anchor = el.get("text-anchor") or inherit.get("text-anchor") or "start"
                pad = max(2, int(round(fpx * 0.10)))
                halo = (255, 255, 255, 255)
                rm = re.search(r"rotate\(\s*([-+0-9.]+)", el.get("transform") or "")
                rot = float(rm.group(1)) if rm else 0.0
                if rot:
                    # 旋转文字：先画到小 tile（含白描边），再旋转拼回，中心对准 (x,y)
                    bb = dr.textbbox((0, 0), txt, font=font, stroke_width=pad)
                    tile = Image.new("RGBA", (bb[2] - bb[0] + 4, bb[3] - bb[1] + 4), (0, 0, 0, 0))
                    td = ImageDraw.Draw(tile)
                    td.text((2 - bb[0], 2 - bb[1]), txt, font=font, fill=tcol,
                            stroke_width=pad, stroke_fill=halo)
                    tile = tile.rotate(-rot, expand=True, resample=Image.BICUBIC)
                    img.alpha_composite(tile, (int(x - tile.width / 2), int(y - tile.height / 2)))
                else:
                    bb = dr.textbbox((0, 0), txt, font=font)
                    if anchor == "middle":
                        x -= (bb[2] - bb[0]) / 2.0
                    elif anchor == "end":
                        x -= (bb[2] - bb[0])
                    # 白描边让中心线/分界线在字下断开（原生 stroke，比逐点循环快得多）
                    dr.text((x - bb[0], y - bb[3]), txt, font=font, fill=tcol,
                            stroke_width=pad, stroke_fill=halo)
        for child in list(el):
            walk(child, st)

    walk(root, {})
    img.save(out_path)
    if preview:
        img.resize((int(img.width / 2), int(img.height / 2)), Image.LANCZOS).save(preview)
    return img.size


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("png")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--preview")
    a = ap.parse_args()
    print(render(a.svg, a.png, a.scale, a.preview))
