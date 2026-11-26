#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe.py — 按行/列打印暗区段，或打印暗像素最多的行/列（定位线段真实位置）

用法：
  python probe.py <img> --thr 160 profile rows 20        # 暗像素最多的前20行
  python probe.py <img> --thr 160 rows 590,530,650        # 指定行打印暗区段
  python probe.py <img> --thr 160 cols 250,1320           # 指定列打印暗区段
  python probe.py <img> --thr 160 crop x0,y0,x1,y1 out.png   # 裁剪放大
"""
import sys

import numpy as np
from PIL import Image


def runs(idxs, gap=3):
    if len(idxs) == 0:
        return []
    out, s, p = [], idxs[0], idxs[0]
    for i in idxs[1:]:
        if i - p > gap:
            out.append((int(s), int(p)))
            s = i
        p = i
    out.append((int(s), int(p)))
    return out


def main():
    args = sys.argv[1:]
    thr = 160
    pos = [a for a in args if not a.startswith("--")]
    for a in args:
        if a.startswith("--thr"):
            thr = int(a.split("=")[1])
    path, mode, arg = pos[0], pos[1], pos[2] if len(pos) > 2 else ""
    im = Image.open(path).convert("L")
    a = np.asarray(im)
    dark = a < thr
    if mode == "profile":
        axis = dark.sum(axis=1) if arg == "rows" else dark.sum(axis=0)
        order = np.argsort(axis)[::-1][: int(arg and pos[3] or 20)]
        print(f"{path} thr={thr} 暗像素最多的{'行' if arg=='rows' else '列'}:")
        for i in sorted(order):
            print(f"  {'y' if arg=='rows' else 'x'}={i} cnt={int(axis[i])} runs={runs(np.nonzero(dark[i, :])[0])[:8]}")
    elif mode in ("rows", "cols"):
        print(f"{path} thr={thr}")
        for v in [int(t) for t in arg.split(",")]:
            if mode == "rows":
                print(f"  行 y={v}: runs={runs(np.nonzero(dark[v, :])[0])}")
            else:
                print(f"  列 x={v}: runs={runs(np.nonzero(dark[:, v])[0])}")
    elif mode == "best":
        # 按“最长连续暗段”排序，找最长的水平/垂直笔画（抗手绘波动与文字干扰）
        n = int(arg) if arg.isdigit() else 20
        best = []
        for y in range(a.shape[0]):
            r = runs(np.nonzero(dark[y, :])[0], gap=12)
            if r:
                w = max(t[1] - t[0] for t in r)
                best.append((w, "row", y, [t for t in r if t[1] - t[0] >= w * 0.8]))
        best.sort(reverse=True)
        print(f"{path} thr={thr} 最长水平笔画 top{n}:")
        for w, kind, y, r in best[:n]:
            print(f"  y={y} 最长段={w} 段={r}")
        x0, y0, x1, y1 = [int(t) for t in arg.split(",")]
        scale = int(pos[4]) if len(pos) > 4 else 2
        crop = Image.open(path).convert("L").crop((x0, y0, x1, y1))
        crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
        crop.save(pos[3])
        print(f"saved {pos[3]} {crop.size}")


if __name__ == "__main__":
    main()
