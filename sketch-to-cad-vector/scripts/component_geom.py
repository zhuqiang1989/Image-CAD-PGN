#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""component_geom.py — 用最大连通域隔离主体轮廓，客观量出：
直径、筒体直段长、长径比、封头深度、人孔/接管伸出方向（在封头尖点内侧还是外侧）。

原理：二值化 → 去照片边框 → 4x 降采样 → 8 邻域连通分量（networkx）→ 取最大分量
（手绘图里筒体+封头+隔板+分界线+接管+支座都是连在一起的，文字和引出线是独立小块）。

用法：python component_geom.py <img> [<img> ...] [--thr 160] [--scale 4]
"""
import sys

import networkx as nx
import numpy as np
from PIL import Image


def _shift(m, dy, dx):
    """零填充平移（np.roll 会首尾环绕，会把左右两端误连成一个连通域）。"""
    out = np.zeros_like(m)
    H, W = m.shape
    ys, xs = max(0, dy), max(0, dx)
    ye, xe = min(H, H + dy), min(W, W + dx)
    out[ys:ye, xs:xe] = m[ys - dy : ye - dy, xs - dx : xe - dx]
    return out


def _modal(vals, bin_size=8):
    """众数（按 bin_size 分箱）：母线位置的稳健估计。"""
    if len(vals) == 0:
        return 0.0
    lo = float(np.min(vals))
    idx = ((np.asarray(vals, dtype=float) - lo) // bin_size).astype(int)
    cnt = np.bincount(idx)
    b = int(np.argmax(cnt))
    lo_i = np.asarray(vals)[idx == b]
    return float(np.median(lo_i)) if len(lo_i) else lo + b * bin_size


def largest_component(dark, s=4, dil=1):
    small = dark[: dark.shape[0] // s * s, : dark.shape[1] // s * s].reshape(
        dark.shape[0] // s, s, dark.shape[1] // s, s
    ).any(axis=(1, 3))
    for _ in range(dil):  # 膨胀：把手绘断笔连上（零填充，不环绕）
        acc = small.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                acc |= _shift(small, dy, dx)
        small = acc
    H, W = small.shape
    g = nx.Graph()
    pts = list(zip(*np.nonzero(small)))
    g.add_nodes_from(pts)
    idx = {p: i for i, p in enumerate(pts)}
    edges = []
    for (y, x) in pts:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                q = (y + dy, x + dx)
                if q in idx and q > (y, x):
                    edges.append(((y, x), q))
    g.add_edges_from(edges)
    comps = sorted(nx.connected_components(g), key=len, reverse=True)
    mask = np.zeros_like(small)
    for p in comps[0]:
        mask[p] = True
    return comps, mask, small.shape, s


def measure(path, thr=160, s=4, dil=1):
    im = Image.open(path).convert("L")
    a = np.asarray(im)
    H, W = a.shape
    dark = a < thr
    # 去贴边噪条
    for y in range(H):
        if (y < 18 or y > H - 18) and dark[y, :].mean() > 0.3:
            dark[y, :] = False
    for x in range(W):
        if (x < 18 or x > W - 18) and dark[:, x].mean() > 0.3:
            dark[:, x] = False
    comps, cmask, (sh, sw), s = largest_component(dark, s, dil)
    comp = comps[0]
    ys = np.array([p[0] for p in comp])
    xs = np.array([p[1] for p in comp])
    x0, x1, y0, y1 = xs.min() * s, xs.max() * s, ys.min() * s, ys.max() * s
    print(f"\n=== {path}  thr={thr}")
    print(f"最大连通域占暗像素 {len(comp)}/{int(dark.sum())//1}，包围盒 x[{x0},{x1}] y[{y0},{y1}]")

    # 只取主体轮廓自身的像素做包络，避免文字/引出线/点划线污染
    big = np.zeros((H, W), dtype=bool)
    big[: cmask.shape[0] * s, : cmask.shape[1] * s] = np.kron(cmask, np.ones((s, s), dtype=bool))
    sub = (dark & big)[y0:y1 + 1, x0:x1 + 1]
    cols = {}
    for c in range(sub.shape[1]):
        r = np.nonzero(sub[:, c])[0]
        if len(r):
            cols[x0 + c] = (y0 + r.min(), y0 + r.max())
    xs_sorted = sorted(cols)
    top = np.array([cols[x][0] for x in xs_sorted])
    bot = np.array([cols[x][1] for x in xs_sorted])
    # 母线 = 上/下包络的众数位置（接管、支座只影响个别列，不影响众数）
    mt, mb = _modal(top, 8), _modal(bot, 8)
    tol = 10
    flat = (np.abs(top - mt) <= tol) & (np.abs(bot - mb) <= tol)
    fx = [x for x, v in zip(xs_sorted, flat) if v]
    if not fx:
        print("!! 找不到母线平台"); return {}
    lsh, rsh = min(fx), max(fx)
    plat = rsh - lsh
    diam = mb - mt
    cy = (mt + mb) / 2.0
    print(f"母线 y={mt:.0f} / {mb:.0f}  直径(母线间距)={diam:.0f}  中心线 y={cy:.0f}  (平台列 {len(fx)})")
    print(f"筒体直段 x[{lsh},{rsh}] 长={plat}  →  长径比(直段/直径)={plat/diam:.2f}")
    # 封头尖点：上包络逼近中心线的最外侧列
    left_head = [x for x in xs_sorted if x < lsh and cols[x][0] > cy - 10]
    right_head = [x for x in xs_sorted if x > rsh and cols[x][0] > cy - 10]
    tip_l = max(left_head) if left_head else lsh
    tip_r = min(right_head) if right_head else rsh
    print(f"封头: 左尖点≈x{tip_l}(深{lsh-tip_l}) 右尖点≈x{tip_r}(深{tip_r-rsh})  "
          f"含封头长={tip_r-tip_l}  →  总长/直径={(tip_r-tip_l)/diam:.2f}")
    print(f"包围盒总长={x1-x0}（含人孔等外伸件）")
    over_l, over_r = tip_l - x0, x1 - tip_r
    print(f"人孔外伸量: 左={over_l}px  右={over_r}px   "
          f"（>0 表示接管伸出封头之外；<0 表示被画进封头内侧 = 方向画反）")
    return dict(diam=diam, plat=plat, ratio=plat / diam, tip_l=tip_l, tip_r=tip_r,
                x0=x0, x1=x1, cy=cy, lsh=lsh, rsh=rsh)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    thr, s, dil = 160, 4, 1
    for a in sys.argv[1:]:
        if a.startswith("--thr"):
            thr = int(a.split("=")[1])
        if a.startswith("--scale"):
            s = int(a.split("=")[1])
        if a.startswith("--dil"):
            dil = int(a.split("=")[1])
    for p in args:
        measure(p, thr, s, dil)
