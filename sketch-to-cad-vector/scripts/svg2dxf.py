#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""svg2dxf.py — 把本技能产出的受限子集 SVG 转成可编辑 DXF（R2018, LWPOLYLINE/TEXT）。

与 render_svg.py 共用解析器，所以同一份 SVG 既能出高清 PNG，也能出 DXF：
  layer CONTOUR(轮廓粗线) / DETAIL(结构细线) / CENTER(点划线) / TEXT(文字)

用法：python svg2dxf.py <in.svg> <out.dxf> [--flip-y]
"""
import argparse
import math
import os
import re
import xml.etree.ElementTree as ET

import ezdxf
from ezdxf.entities.text import TextEntityAlignment as TA

from render_svg import qname, style_of, path_segments, pt, color_of  # noqa: E402
from cadkit import arc_center  # noqa: E402

ALIGN = {"start": TA.LEFT, "middle": TA.MIDDLE_CENTER, "end": TA.MIDDLE_RIGHT}

LAYERS = [
    ("CONTOUR", 7, 0.35),
    ("DETAIL", 7, 0.18),
    ("CENTER", 3, 0.13),
    ("TEXT", 7, 0.20),
]

# 中文标注必须用带中日韩字形的 TTF 字体：ezdxf 自带的 Standard 样式指向 txt.shx，
# 只覆盖 ASCII，AutoCAD/中望打开就把中文全画成 "?"。
TEXT_STYLE = "CADHZ"
TEXT_FONTS = ["simhei.ttf", "msyh.ttf", "arialuni.ttf", "simsun.ttf"]


def pick_layer(style, tag):
    if tag == "text":
        return "TEXT"
    if "dash" in style:
        return "CENTER"
    return "CONTOUR" if float(style.get("stroke-width", 1)) >= 3.2 else "DETAIL"


_NUM = r"[-+]?(?:\d*\.\d+|\d+)"
_CIRCLE_RE = re.compile(
    rf"M\s*({_NUM})\s+({_NUM})\s+A\s*({_NUM})\s+({_NUM})\s+0\s+1\s+0\s+({_NUM})\s+({_NUM})"
    rf"\s+A\s*({_NUM})\s+({_NUM})\s+0\s+1\s+0\s+({_NUM})\s+({_NUM})\s*Z?\s*")


def try_circle(msp, d, T, layer):
    """cadkit 的整圆（两段 A 弧拼成）→ 真正的 CIRCLE 实体；非圆返回 False 走折线。"""
    m = _CIRCLE_RE.fullmatch(d.strip())
    if not m:
        return False
    x0, y0, rx, ry, x1, y1, _a, _b, _c, _d = map(float, m.groups())
    if abs(rx - ry) > 0.5:
        return False
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    msp.add_circle(T(cx, cy), rx, dxfattribs={"layer": layer})
    return True


_ARC_RE = re.compile(
    rf"M\s*({_NUM})\s+({_NUM})\s+A\s*({_NUM})\s+({_NUM})\s+({_NUM})\s+([01])\s+([01])\s+({_NUM})\s+({_NUM})\s*")


def try_arc(msp, d, T, layer):
    """cadkit 单段椭圆弧 → 真正的 ELLIPSE/ARC 实体（y 翻转后角度取负）。"""
    m = _ARC_RE.fullmatch(d.strip())
    if not m:
        return False
    x0, y0, rx, ry, rot, laf, sf, x1, y1 = map(float, m.groups())
    cx, cy, th1, dth = arc_center(x0, y0, rx, ry, rot, laf, sf, x1, y1)
    if abs(rx - ry) < 0.5:
        s, en = th1, th1 + dth
        if dth < 0:
            s, en = en, s
        msp.add_arc(T(cx, cy), rx, math.degrees(-en), math.degrees(-s), dxfattribs={"layer": layer})
    else:
        major = max(rx, ry)
        ratio = min(rx, ry) / major
        if rx >= ry:
            axis = (major, 0, 0)
            sp, ep = th1, th1 + dth
        else:
            axis = (0, -major, 0)
            sp, ep = th1 - math.pi / 2, th1 + dth - math.pi / 2
        if dth < 0:
            sp, ep = ep, sp
        msp.add_ellipse(T(cx, cy), major_axis=axis, ratio=ratio,
                        start_param=-ep, end_param=-sp, dxfattribs={"layer": layer})
    return True


def convert(svg_path, dxf_path, flip_y=True, version="R2018"):
    root = ET.parse(svg_path).getroot()
    vb = pt(root.get("viewBox") or "0 0 100 100")
    h = float(root.get("height") or vb[3])
    doc = ezdxf.new(version, setup=True)
    msp = doc.modelspace()
    for name, color, lw in LAYERS:
        if name not in doc.linetypes and name != "CENTER":
            pass
        doc.layers.add(name, color=color, lineweight=int(lw * 100))
        if name == "CENTER":
            doc.layers.get("CENTER").dxf.linetype = "CENTER"  # ezdxf setup=True 自带点划线

    def T(x, y):
        return (x, h - y) if flip_y else (x, y)

    # 中文文字样式：TTF + 扩展字体信息（家族名），这样 CAD 才能显示中文而不是 "?"
    import os

    font_file = next((f for f in TEXT_FONTS if os.path.exists(os.path.join(r"C:\Windows\Fonts", f))),
                     "simhei.ttf")
    fam = {"simhei.ttf": "SimHei", "msyh.ttf": "Microsoft YaHei",
           "arialuni.ttf": "Arial Unicode MS", "simsun.ttf": "SimSun"}[font_file]
    if TEXT_STYLE not in doc.styles:
        st = doc.styles.add(TEXT_STYLE, font=font_file)
        st.set_extended_font_data(family=fam, italic=False, bold=False)
    doc.styles.get(TEXT_STYLE).dxf.font = font_file
    doc.header["$TEXTSTYLE"] = TEXT_STYLE
    doc.header["$INSUNITS"] = 0

    def walk(el, inherit):
        st = style_of(el, inherit)
        tag = qname(el.tag)
        layer = pick_layer(st, tag)
        if tag == "line":
            x1, y1, x2, y2 = (float(el.get(k, 0)) for k in ("x1", "y1", "x2", "y2"))
            msp.add_line(T(x1, y1), T(x2, y2), dxfattribs={"layer": layer})
        elif tag == "rect":
            x, y = float(el.get("x", 0)), float(el.get("y", 0))
            w, hh = float(el.get("width", 0)), float(el.get("height", 0))
            pts = [T(x, y), T(x + w, y), T(x + w, y + hh), T(x, y + hh)]
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})
        elif tag in ("polyline", "polygon"):
            raw = pt(el.get("points", ""))
            pts = [T(raw[i], raw[i + 1]) for i in range(0, len(raw) - 1, 2)]
            msp.add_lwpolyline(pts, close=(tag == "polygon"), dxfattribs={"layer": layer})
        elif tag == "path":
            filled = bool(color_of(st.get("fill")))
            d = el.get("d", "")
            if not filled and (try_circle(msp, d, T, layer) or try_arc(msp, d, T, layer)):
                pass  # 整圆/弧已用 CIRCLE/ELLIPSE/ARC 真实体输出
            else:
                for sub in path_segments(d):
                    if len(sub) > 1:
                        closed = (len(sub) > 2 and abs(sub[0][0] - sub[-1][0]) < 0.5
                                  and abs(sub[0][1] - sub[-1][1]) < 0.5)
                        pts = [T(x, y) for x, y in sub]
                        msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": layer})
                        if filled and closed:  # 实心填充（焊口点/箭头）→ SOLID hatch
                            h = msp.add_hatch(color=256, dxfattribs={"layer": layer})
                            h.paths.add_polyline_path(pts, is_closed=True)
                            h.set_solid_fill(color=256)
        elif tag == "text":
            txt = "".join(el.itertext()).strip()
            if txt:
                x, y = float(el.get("x", 0)), float(el.get("y", 0))
                size = float(st["font-size"])
                align = ALIGN.get(el.get("text-anchor") or inherit.get("text-anchor") or "start", TA.LEFT)
                rm = re.search(r"rotate\(\s*([-+0-9.]+)", el.get("transform") or "")
                rot = float(rm.group(1)) if rm else 0.0
                if rot:
                    align = TA.MIDDLE_CENTER
                t = msp.add_text(
                    txt, height=size, rotation=rot,
                    dxfattribs={"layer": "TEXT", "style": TEXT_STYLE},
                )
                t.set_placement(T(x, y), align=align)
        for child in list(el):
            walk(child, st)

    walk(root, {})
    for e in msp:  # 全部随层：改层线型/线宽即可整体调整
        e.dxf.linetype = "BYLAYER"
        e.dxf.color = 256  # BYLAYER
    doc.header["$INSUNITS"] = 0
    doc.saveas(dxf_path)
    return len(msp)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("dxf")
    ap.add_argument("--no-flip-y", dest="flip_y", action="store_false")
    ap.add_argument("--dxf-version", default="R2018", help="R2018/R2010/R2000…（ezdxf 一律按 UTF-8 写文件，"
                                                          "老 CAD 只认 GBK 时请在 CAD 内 DWGOUT 另存）")
    a = ap.parse_args()
    n = convert(a.svg, a.dxf, a.flip_y, a.dxf_version)
    print(f"{os.path.basename(a.dxf)}: {n} entities  [{a.dxf_version}]  文字样式 {TEXT_STYLE}→simhei.ttf")
