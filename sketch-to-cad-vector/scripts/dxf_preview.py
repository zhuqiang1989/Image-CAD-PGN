#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dxf_preview.py — 把 DXF 渲染回 PNG（视觉自检 / 验证真实体几何）

用 ezdxf.disassemble 把 LINE/ARC/ELLIPSE/CIRCLE/LWPOLYLINE 等 tessellate 成折线，
Pillow 绘制；TEXT 按位置/旋转/字高单独画。不依赖 matplotlib。

用法：python dxf_preview.py <in.dxf> <out.png> [--width 1200]
"""
import argparse
import math

import ezdxf
from ezdxf import bbox
from ezdxf.disassemble import make_primitive
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\simhei.ttf"


def render(dxf_path, out_path, width=1200):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    ext = bbox.extents(msp, fast=True)
    if not ext.has_data:
        raise SystemExit("empty DXF")
    minx, miny = ext.extmin.x, ext.extmin.y
    maxx, maxy = ext.extmax.x, ext.extmax.y
    w, h = maxx - minx, maxy - miny
    margin = 0.04 * max(w, h)
    scale = (width - 2 * margin * width / max(w, h)) / max(w, h)
    pad = int(margin * scale)
    iw = int(w * scale) + 2 * pad
    ih = int(h * scale) + 2 * pad
    img = Image.new("RGB", (iw, ih), "white")
    dr = ImageDraw.Draw(img)

    def P(x, y):
        return (pad + (x - minx) * scale, pad + (maxy - y) * scale)

    for e in msp:
        t = e.dxftype()
        if t == "TEXT":
            txt = e.dxf.text
            height = e.dxf.height * scale
            try:
                font = ImageFont.truetype(FONT, max(6, int(height)))
            except OSError:
                font = ImageFont.load_default()
            align = e.get_placement()
            pt = align[1]
            px, py = P(pt.x, pt.y)
            rot = e.dxf.rotation
            bb = dr.textbbox((0, 0), txt, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            tile = Image.new("RGBA", (tw + 4, th + 4), (0, 0, 0, 0))
            td = ImageDraw.Draw(tile)
            td.text((2 - bb[0], 2 - bb[1]), txt, font=font, fill="black")
            if rot:
                tile = tile.rotate(rot, expand=True, resample=Image.BICUBIC)
            img.paste(tile, (int(px - tile.width / 2), int(py - tile.height / 2)), tile)
            continue
        if t == "HATCH":
            for path in e.paths:
                try:
                    verts = path.vertices if hasattr(path, "vertices") else []
                    pts = [P(v[0], v[1]) for v in verts]
                    if len(pts) > 2:
                        dr.polygon(pts, fill="black")
                except Exception:
                    pass
            continue
        try:
            prim = make_primitive(e)
        except Exception:
            continue
        verts = getattr(prim, "vertices", None)
        if callable(verts):
            verts = verts()
        if not verts:
            continue
        pts = [P(v.x, v.y) for v in verts]
        if len(pts) > 1:
            dr.line(pts, fill="black", width=2)
    img.save(out_path)
    return img.size


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dxf")
    ap.add_argument("png")
    ap.add_argument("--width", type=int, default=1200)
    a = ap.parse_args()
    print(render(a.dxf, a.png, a.width))