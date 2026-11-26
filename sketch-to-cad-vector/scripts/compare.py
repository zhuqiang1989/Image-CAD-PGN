#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compare.py — 成品与原图叠比对（视觉自检，零生图模型）

把原图淡化成浅灰底，把成品线稿叠成红色，输出叠加图 + 左右并排图，便于肉眼核对
"主体轮廓/部件位置/文字"是否与原图一致。示意级重绘不追求像素级对齐（几何已归一化），
叠比对用于确认拓扑与部件落位大致吻合、有无漏画/错画。

用法：python compare.py <原图> <成品.png> <out_overlay.png> [--side <out_side.png>]
依赖：Pillow。
"""
import argparse
from PIL import Image


def overlay(original, result, out):
    res = Image.open(result).convert("RGBA")
    W, H = res.size
    orig = Image.open(original).convert("L").resize((W, H))
    # 原图淡化：黑线→浅灰，白底→白
    bg = orig.point(lambda v: 255 - int((255 - v) * 0.30)).convert("RGB")
    px = bg.load()
    rp = res.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = rp[x, y]
            if a > 0 and max(r, g, b) < 140:
                px[x, y] = (215, 40, 40)
    bg.save(out)
    return W, H


def side_by_side(original, result, out):
    res = Image.open(result).convert("RGB")
    W, H = res.size
    orig = Image.open(original).convert("RGB").resize((W, H))
    canvas = Image.new("RGB", (W * 2 + 20, H), "white")
    canvas.paste(orig, (0, 0))
    canvas.paste(res, (W + 20, 0))
    canvas.save(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("result")
    ap.add_argument("out")
    ap.add_argument("--side")
    a = ap.parse_args()
    W, H = overlay(a.original, a.result, a.out)
    msg = f"叠比对 {a.out}（{W}×{H}，红=成品线，浅灰=原图）"
    if a.side:
        side_by_side(a.original, a.result, a.side)
        msg += f" + 并排 {a.side}"
    print(msg)