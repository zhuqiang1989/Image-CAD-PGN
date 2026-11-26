#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dxf_check.py — 复查 DXF 的文字能否在中望/AutoCAD 里显示（问号 = 字体问题）

检查：$TEXTSTYLE、样式引用的字体文件是否存在、TTF 扩展字体信息、每个 TEXT 实体的样式与内容。

用法：python dxf_check.py <file.dxf>
"""
import os
import sys

import ezdxf

FONT_DIRS = [r"C:\Windows\Fonts"]


def main(path):
    doc = ezdxf.readfile(path)
    print(f"文件: {os.path.basename(path)}  DXF版本={doc.dxfversion}  codepage={doc.header.get('$DWGCODEPAGE')}")
    print(f"$TEXTSTYLE = {doc.header.get('$TEXTSTYLE')}")
    used = set()
    msp0 = doc.modelspace()
    for e in msp0:
        if e.dxftype() in ("TEXT", "MTEXT"):
            used.add(e.dxf.style)
    for st in doc.styles:
        if st.dxf.name not in used and st.dxf.name != doc.header.get("$TEXTSTYLE"):
            continue
        f = st.dxf.font or ""
        where = next((os.path.join(d, f) for d in FONT_DIRS if f and os.path.exists(os.path.join(d, f))), None)
        fam = "-"
        xd = getattr(st, "xdata", None)
        if xd is not None:
            data = getattr(xd, "data", None)
            pairs = list(data.items()) if isinstance(data, dict) else (list(data()) if callable(data) else [])
            for _code, vals in pairs:
                vs = vals if isinstance(vals, (list, tuple)) else [vals]
                strs = [str(v) for v in vs if isinstance(v, str)]
                if strs:
                    fam = strs[0]
                    break
        print(f"  样式 {st.dxf.name:<10} font={f:<16} bigfont={st.dxf.bigfont!r:<6} "
              f"家族={fam:<18} 本机字体文件={'有' if where else '无'}")
    msp = doc.modelspace()
    texts = [e for e in msp if e.dxftype() == "TEXT"]
    print(f"TEXT 实体 {len(texts)} 个，引用样式: {sorted({e.dxf.style for e in texts})}")
    for e in texts:
        print(f"   [{e.dxf.layer}] {e.dxf.style:<7} 高={e.dxf.height:.0f}  {e.dxf.text}")
    bad = [e.dxf.text for e in texts if any(ord(c) > 127 for c in e.dxf.text)
           and not os.path.exists(os.path.join(FONT_DIRS[0], doc.styles.get(e.dxf.style).dxf.font or "x"))]
    print("中文标注字体可用性:", "OK" if not bad else f"缺失 -> {bad}")


if __name__ == "__main__":
    main(sys.argv[1])
