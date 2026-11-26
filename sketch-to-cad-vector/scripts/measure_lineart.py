#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""measure_lineart.py — 线稿几何量测（用来核对重绘是否走样，不靠肉眼）

打印：主体上下母线、筒体直段长度、封头深度、长径比、顶部/底部接管位置与伸出长度、
两端侧向接管（人孔）方向（朝外还是朝内）。

用法：python measure_lineart.py <img> [<img> ...] [--thr 128]
"""
import sys

import numpy as np
from PIL import Image


def clusters(idxs, gap=6):
    if not idxs:
        return []
    out, s, p = [], idxs[0], idxs[0]
    for i in idxs[1:]:
        if i - p > gap:
            out.append((s, p))
            s = i
        p = i
    out.append((s, p))
    return out


def measure(path, thr=128):
    im = Image.open(path).convert("L")
    a = np.asarray(im)
    H, W = a.shape
    dark = a < thr
    # 去掉照片黑边/满行满列（整行几乎全黑视为扫描边框）
    rowf = dark.mean(axis=1)
    colf = dark.mean(axis=0)
    dark[rowf > 0.85, :] = False
    dark[:, colf > 0.85] = False
    # 再去掉贴边的黑块（照片阴影）：距边 2% 以内
    mx, my = int(W * 0.02), int(H * 0.02)
    dark[:my, :] = False
    dark[-my:, :] = False
    dark[:, :mx] = False
    dark[:, -mx:] = False

    ys, xs = np.nonzero(dark)
    if len(xs) == 0:
        print(path, "no dark pixels"); return
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    print(f"\n=== {path}")
    print(f"尺寸 {W}x{H}  内容包围盒 x[{x0},{x1}] y[{y0},{y1}]  ({bw}x{bh})")

    # 长横线（筒体上下母线）：手绘线有波动，按行覆盖率聚类成带
    hbands = []
    for y in range(y0, y1 + 1):
        xs2 = np.nonzero(dark[y, x0:x1 + 1])[0]
        if len(xs2) > 0.35 * bw:
            run_x = max(clusters(list(xs2), gap=8), key=lambda t: t[1] - t[0])
            hbands.append((y, len(xs2), x0 + run_x[0], x0 + run_x[1]))
    grp = []
    for y, c, rx0, rx1 in hbands:
        if grp and y - grp[-1][0][-1] <= 6:
            grp[-1][0].append(y)
            grp[-1][1] = max(grp[-1][1], c)
            grp[-1][2] = min(grp[-1][2], rx0)
            grp[-1][3] = max(grp[-1][3], rx1)
        else:
            grp.append([[y], c, rx0, rx1])
    print("长横线带(>35%%宽): %s" % [(g[0][0], g[0][-1], int(g[1]), int(g[2]), int(g[3])) for g in grp])
    tops = [(g[0][0] + g[0][-1]) // 2 for g in grp]
    if len(tops) < 2:
        print("!! 母线不足两条，可能阈值或图不对"); return
    st, sb = tops[0], tops[-1]

    # 长竖线
    vlines = []
    for x in range(x0, x1 + 1):
        cnt = int(dark[y0:y1 + 1, x].sum())
        if cnt > 0.35 * (sb - st):
            vlines.append((x, cnt))
    vgrp = []
    for x, c in vlines:
        if vgrp and x - vgrp[-1][-1] <= 4:
            vgrp[-1].append(x)
        else:
            vgrp.append([x])
    print("长竖线(>35%%高): %s" % [(g[0], g[-1]) for g in vgrp])

    # 筒体直段：母线自身覆盖的 x 范围（不含引出线/文字）
    def run_of(row):
        xs2 = np.nonzero(dark[row, :])[0]
        cs = clusters(list(xs2), gap=4)
        return max(cs, key=lambda t: t[1] - t[0]) if cs else (0, 0)
    ls, le = run_of(st)
    straight = le - ls
    diam = sb - st
    # 封头最外端：在上下母线之间（含中心带）最左/最右暗像素
    band = dark[st + 8:sb - 8, :]
    bxs = np.nonzero(band.any(axis=0))[0]
    tips = clusters(list(bxs), gap=4)
    print(f"筒体直段 x[{ls},{le}] 长={straight}   直径(母线间距)={diam}   长径比(直段/直径)={straight/diam:.2f}")
    print(f"含封头总宽 最左={bxs.min()} 最右={bxs.max()} 总长={bxs.max()-bxs.min()}  总长/直径={(bxs.max()-bxs.min())/diam:.2f}")
    if tips:
        print(f"  暗区横向分块: {tips}")

    # 顶部接管：母线上方的暗区聚类（排除文字：文字块与母线不相接）
    def attach(top_row, bot_row, side):
        sub = dark[top_row:bot_row, :]
        if not sub.any():
            return
        cs = clusters(list(np.nonzero(sub.any(axis=0))[0]), gap=8)
        print(f"{side}接管带 x 聚类:")
        for a_, b_ in cs:
            colrows = np.nonzero(sub[:, a_:b_ + 1].any(axis=1))[0]
            print(f"   x[{a_},{b_}] 宽{b_-a_+1}  距母线{'上' if side.startswith('顶') else '下'}"
                  f"{abs(colrows.min()) if side.startswith('顶') else ''}"
                  f" 伸出像素高={colrows.max()-colrows.min()+1} 范围y[{top_row+colrows.min()},{top_row+colrows.max()}]")
    attach(max(0, y0), st - 4, "顶部")
    attach(sb + 5, min(y1, y1) + 1, "底部")

    # 侧向接管：母线带内在主体最左/最右之外的暗区
    inner_l, inner_r = bxs.min(), bxs.max()
    left_of = dark[st:sb + 1, :inner_l]
    right_of = dark[st:sb + 1, inner_r + 1:]
    def side_info(sub, name, base):
        if not sub.any():
            print(f"{name}侧: 无暗区（接管未伸出封头）"); return
        cs = clusters(list(np.nonzero(sub.any(axis=0))[0]), gap=8)
        print(f"{name}侧(封头外) 暗块: {[(a+base, b+base, b-a+1) for a, b in cs]}")
    side_info(left_of, "左", 0)
    side_info(right_of, "右", inner_r + 1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    thr = 128
    for a in sys.argv[1:]:
        if a.startswith("--thr"):
            thr = int(a.split("=")[1])
    for p in args:
        measure(p, thr)
