#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""merge_dxf.py — 把多个 DXF 合并到一个文件（批量处理"统一绘制"选项）

每张图按网格错开摆放，互不重叠；保留各自图层/线型/文字样式（含 CADHZ 中文样式）。
"分开绘制"选项无需本脚本——build.ps1 默认每张图各出一个 DXF。

用法：
    python merge_dxf.py a.dxf b.dxf c.dxf -o merged.dxf [--cols 2] [--gap 60]
"""
import argparse

import ezdxf
from ezdxf import bbox
from ezdxf.addons.importer import Importer


def merge(paths, out, cols=2, gap=60.0):
    dst = ezdxf.new("R2018", setup=True)
    msp = dst.modelspace()
    x_cur, y_cur, row_h, col = 0.0, 0.0, 0.0, 0
    for p in paths:
        src = ezdxf.readfile(p)
        ext = bbox.extents(src.modelspace(), fast=True)
        if not ext.has_data:
            continue
        w, h = ext.size.x, ext.size.y
        # 让本图顶边对齐 y_cur、左边对齐 x_cur，向下/向右铺排
        dx = x_cur - ext.extmin.x
        dy = y_cur - ext.extmax.y
        before = len(msp)
        imp = Importer(src, dst)
        imp.import_modelspace()
        imp.finalize()
        for e in list(msp)[before:]:
            try:
                e.translate(dx, dy, 0)
            except Exception:
                pass
        col += 1
        if col >= cols:
            col = 0
            x_cur = 0.0
            y_cur -= (row_h + gap)
            row_h = 0.0
        else:
            x_cur += w + gap
        row_h = max(row_h, h)
    if "CADHZ" in dst.styles:
        dst.header["$TEXTSTYLE"] = "CADHZ"
    dst.saveas(out)
    return len(msp)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--gap", type=float, default=60.0)
    a = ap.parse_args()
    n = merge(a.inputs, a.out, a.cols, a.gap)
    print(f"已合并 {len(a.inputs)} 个 DXF → {a.out}（{n} 实体，{a.cols} 列网格错开）")