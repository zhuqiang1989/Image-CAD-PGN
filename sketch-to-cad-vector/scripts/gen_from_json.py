#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_from_json.py — 语义 JSON → CAD 线稿（读图与绘制解耦）

判读阶段把结论写成结构化 JSON（对象 + 归一化/像素参数 + 文字清单），绘制阶段由本
脚本消费 JSON 调 cadkit 同源出 SVG+DXF。改判读只改 JSON，不必碰绘制代码。

支持三种 type：
  · vessel     高层容器 schema（壳体/封头/接管/人孔/管板/内部/铭牌/中心线/标注）
  · isometric  高层单线图 schema（管线 runs/焊口/阀门/放空/大小头/箭头/折断/标注/表头/指北针）
  · primitives 通用图元回放（任意类型兜底，直接列 cadkit 图元）

用法：python gen_from_json.py <spec.json> <out.svg> [--dxf <out.dxf>]
schema 详见 references/semantic-json.md。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cadkit import SVG  # noqa: E402


def build_vessel(d):
    w, h = d["canvas"]
    s = SVG(w, h)
    sh = d["shell"]
    tb, bot, ts = sh["top_big"], sh["bottom"], sh["top_small"]
    xjl, xjr = sh["x_big_left"], sh["x_big_right"]
    xsl, xsr = sh["x_small_left"], sh["x_small_right"]
    cyb = (tb + bot) / 2
    cys = (ts + bot) / 2
    for cl in d.get("centerlines", []):
        s.centerline(*cl)
    s.line(xjl, tb, xjr, tb, 4)
    s.line(xsl, bot, xjr, bot, 4)
    hb = d["heads"]
    s.arc(xjr, tb, hb["right_depth"], (bot - tb) / 2, xjr, bot, sweep=1, w=4)
    s.line(xsl, ts, xsr, ts, 4)
    s.arc(xsl, ts, hb["left_depth"], (bot - ts) / 2, xsl, bot, sweep=0, w=4)
    s.line(xsr, ts, xjl, tb, 4)
    for x, y0 in ((xsl, ts), (xsr, ts), (xjl, tb), (xjr, tb)):
        s.line(x, y0, x, bot, 2.6)
    for x in d.get("tubesheets_small", []):
        s.line(x - 3, ts, x - 3, bot, 2.2); s.line(x + 3, ts, x + 3, bot, 2.2)
    for x in d.get("tubesheets_big", []):
        s.line(x - 3, tb, x - 3, bot, 2.2); s.line(x + 3, tb, x + 3, bot, 2.2)
    for it in d.get("internals", []):
        x, y0, y1, r = it["x"], it["y0"], it["y1"], it.get("r", 5)
        s.hidden(x, y0 + r, x, y1 - r)
        s.circle(x, y0, r, 2.0); s.circle(x, y1, r, 2.0)
    for c in d.get("circles", []):
        s.circle(c["x"], c["y"], c["r"], c.get("w", 2.2))
    np = d.get("nameplate")
    if np:
        s.rect(*np["rect"], 2.2); s.text(np["x"], np["y"], np.get("text", "铭牌"), np.get("size", 16))
    for m in d.get("manholes", []):
        ang = m["ang"]
        s.nozzle(m["x"], m["y"], ang, m.get("bore", 28), m.get("len", 20), flange=False)
        s.rect(*m["flange"], 2.8)
    for n in d.get("nozzles_top", []):
        s.nozzle(n["x"], n.get("root", tb), -90, n.get("bore", 22), n.get("len", 17))
    for n in d.get("nozzles_bottom", []):
        s.nozzle(n["x"], n.get("root", bot), 90, n.get("bore", 22), n.get("len", 20))
    for t in d.get("labels", []):
        s.text(t["x"], t["y"], t["text"], t.get("size", 18), t.get("anchor", "middle"))
    for ld in d.get("leaders", []):
        s.leader(*ld)
    return s


def build_isometric(d):
    w, h = d["canvas"]
    s = SVG(w, h)
    for r in d.get("runs", []):
        s.poly([tuple(p) for p in r["points"]], r.get("w", 2.4))
    for ln in d.get("lines", []):
        s.line(*ln["pts"], ln.get("w", 2.2))
    for c in d.get("weld_circles", []):
        s.circle(c["cx"], c["cy"], c["r"], 2.2)
    for wd in d.get("welds", []):
        s.dot(wd["x"], wd["y"], wd.get("r", 5))
    for v in d.get("valves", []):
        s.valve(v["x"], v["y"], v.get("ang", 90), v.get("bw", 16), v.get("bh", 14),
                flanged=v.get("flanged", False))
    for vt in d.get("vents", []):
        bx, by = vt["base"]
        s.line(bx, by, bx, by - vt.get("len", 52), 2.2)
        s.valve(bx, by - vt.get("len", 52) - 6, 90, 16, 14, flanged=True)
    for rd in d.get("reducers", []):
        s.reducer(rd["x"], rd["y"], rd.get("ang", 0), rd.get("w1", 18), rd.get("w2", 10), rd.get("len", 16))
    for a in d.get("arrows", []):
        s.arrow(a["x"], a["y"], a.get("ang", 0), a.get("size", 11))
    for b in d.get("breaklines", []):
        s.breakline(b["x"], b["y"], b.get("ang", 0), b.get("width", 20))
    for t in d.get("labels", []):
        s.text(t["x"], t["y"], t["text"], t.get("size", 16), t.get("anchor", "middle"), t.get("rot", 0))
    cp = d.get("compass")
    if cp:
        cx, cy = cp["center"]
        import math
        for arm in cp["arms"]:
            ang = arm["ang"]
            ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            tx, ty = cx + ux * cp.get("r", 40), cy + uy * cp.get("r", 40)
            s.line(cx, cy, tx, ty, 1.8); s.arrow(tx, ty, ang, 9)
            s.text(arm["lx"], arm["ly"], arm["label"], 17)
    return s


def build_primitives(d):
    w, h = d["canvas"]
    s = SVG(w, h)
    for e in d.get("primitives", []):
        k = e["kind"]
        if k == "line":
            s.line(e["x1"], e["y1"], e["x2"], e["y2"], e.get("w", 2.6), e.get("dash"))
        elif k == "poly":
            s.poly([tuple(p) for p in e["pts"]], e.get("w", 2.6), e.get("close", False), e.get("dash"), e.get("fill"))
        elif k == "rect":
            s.rect(e["x"], e["y"], e["w"], e["h"], e.get("sw", 2.6))
        elif k == "arc":
            s.arc(e["x0"], e["y0"], e["rx"], e["ry"], e["x1"], e["y1"], e.get("sweep", 0), e.get("w", 4))
        elif k == "circle":
            s.circle(e["cx"], e["cy"], e["r"], e.get("w", 2.6), e.get("fill"))
        elif k == "ellipse":
            s.ellipse(e["cx"], e["cy"], e["rx"], e["ry"], e.get("w", 2.6), e.get("fill"))
        elif k == "dot":
            s.dot(e["cx"], e["cy"], e.get("r", 5))
    for t in d.get("texts", []):
        s.text(t["x"], t["y"], t["text"], t.get("size", 28), t.get("anchor", "middle"), t.get("rot", 0))
    return s


BUILDERS = {"vessel": build_vessel, "isometric": build_isometric, "primitives": build_primitives}


def build(spec):
    return BUILDERS[spec["type"]](spec)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--dxf")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    s = build(spec)
    s.save_svg(a.out)
    msg = f"已生成 {a.out}（type={spec['type']}）"
    if a.dxf:
        n = s.save_dxf(a.dxf)
        msg += f" + {a.dxf}（{n} 实体，同源直出）"
    print(msg)