#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""cadkit.py — 通用 CAD 线稿绘图原语（同源直出 SVG 预览 + DXF 真实体）

模型读懂图后写一个很短的脚本调用这些原语。内部维护一份**结构化图元列表**，
同一份图元同源输出两种产物：
  · save_svg(path)：受限子集 SVG，供 render_svg.py 出 PNG 预览。
  · save_dxf(path)：直接用 ezdxf 发原生实体 LINE/LWPOLYLINE/CIRCLE/ELLIPSE/ARC/
    TEXT/HATCH，不再解析 SVG，弧/圆/文字都是一等实体（更正规、可编辑）。

约定：坐标=画布像素，y 轴向下（SVG）；角度 0=+x(右)、90=+y(下)，顺时针为正。
线宽分层：轮廓 4 / 结构 2.6–3 / 内部 2.2 / 中心线 1.6 点划线 / 隐藏 2.2 虚线。
"""
import math

# ---- DXF 可选依赖（仅 save_dxf 需要）----
try:
    import ezdxf
    from ezdxf.entities.text import TextEntityAlignment as TA
    _HAS_EZDXF = True
except Exception:  # pragma: no cover
    _HAS_EZDXF = False


def _u(ang):
    a = math.radians(ang)
    return math.cos(a), math.sin(a)


def arc_center(x0, y0, rx, ry, rot_deg, laf, sf, x1, y1):
    """SVG 端点法椭圆弧 → 中心参数 (cx, cy, th1, dth)（SVG 坐标系，弧度）。"""
    rx, ry = abs(float(rx)), abs(float(ry))
    if rx == 0 or ry == 0:
        return (x1, y1, 0.0, 0.0)
    phi = math.radians(rot_deg)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x0 - x1) / 2.0, (y0 - y1) / 2.0
    x1p = cp * dx + sp * dy
    y1p = -sp * dx + cp * dy
    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:
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
    return cx, cy, th1, dth


class SVG:
    def __init__(self, w, h):
        self.w, self.h = int(w), int(h)
        self.p = []          # 结构化图元列表（唯一几何源）
        self.t = []          # 文字图元

    # ---- 基础几何（记录图元）----
    def line(self, x1, y1, x2, y2, w=2.6, dash=None):
        self.p.append(dict(kind="line", x1=x1, y1=y1, x2=x2, y2=y2, w=w, dash=dash))

    def poly(self, pts, w=2.6, close=False, dash=None, fill=None):
        self.p.append(dict(kind="poly", pts=list(pts), w=w, close=close, dash=dash, fill=fill))

    def rect(self, x, y, w, h, sw=2.6):
        self.p.append(dict(kind="rect", x=x, y=y, w=w, h=h, sw=sw))

    def path(self, d, w=2.6, fill=None, dash=None):
        self.p.append(dict(kind="path", d=d, w=w, fill=fill, dash=dash))

    def arc(self, x0, y0, rx, ry, x1, y1, sweep=0, w=4, rot=0, laf=0):
        self.p.append(dict(kind="arc", x0=x0, y0=y0, rx=rx, ry=ry, x1=x1, y1=y1,
                           sweep=sweep, w=w, rot=rot, laf=laf))

    def ellipse(self, cx, cy, rx, ry, w=2.6, fill=None):
        self.p.append(dict(kind="ellipse", cx=cx, cy=cy, rx=rx, ry=ry, w=w, fill=fill))

    def circle(self, cx, cy, r, w=2.6, fill=None):
        self.ellipse(cx, cy, r, r, w, fill)

    def dot(self, cx, cy, r=5):
        self.ellipse(cx, cy, r, r, w=1, fill="#000000")

    def centerline(self, x1, y1, x2, y2):
        self.line(x1, y1, x2, y2, 1.6, "34 9 6 9")

    def hidden(self, x1, y1, x2, y2, w=2.2):
        self.line(x1, y1, x2, y2, w, "12 7")

    def text(self, x, y, s, size=28, anchor="middle", rot=0):
        self.t.append(dict(kind="text", x=x, y=y, s=s, size=size, anchor=anchor, rot=rot))

    # ---- 工程符号 ----
    def valve(self, cx, cy, ang=90, bw=22, bh=20, flanged=False, handwheel=False, w=2.6):
        ux, uy = _u(ang)
        px, py = -uy, ux
        for sgn in (1, -1):
            bx, by = cx + ux * bh / 2 * sgn, cy + uy * bh / 2 * sgn
            self.poly([(cx, cy), (bx + px * bw / 2, by + py * bw / 2),
                       (bx - px * bw / 2, by - py * bw / 2)], w, close=True)
        if handwheel:
            sx, sy = cx + px * (bh * 0.9), cy + py * (bh * 0.9)
            self.line(cx, cy, sx, sy, 2.2)
            self.line(sx - ux * bw * 0.4, sy - uy * bw * 0.4, sx + ux * bw * 0.4, sy + uy * bw * 0.4, 3)
        if flanged:
            self.flange_marks(cx, cy, ang, gap=bh / 2 + 6, fl=bw * 0.7)

    def flange_marks(self, cx, cy, ang=90, gap=16, fl=16, w=2.2):
        ux, uy = _u(ang)
        px, py = -uy, ux
        for sgn in (1, -1):
            for off in (0, 3):
                d = gap + off
                mx, my = cx + ux * d * sgn, cy + uy * d * sgn
                self.line(mx - px * fl / 2, my - py * fl / 2, mx + px * fl / 2, my + py * fl / 2, w)

    def flange_face(self, cx, cy, ang=0, width=30, w=3):
        px, py = -_u(ang)[1], _u(ang)[0]
        self.line(cx - px * width / 2, cy - py * width / 2, cx + px * width / 2, cy + py * width / 2, w)

    def breakline(self, cx, cy, ang=0, width=24, amp=5, w=2.2):
        px, py = -_u(ang)[1], _u(ang)[0]
        ux, uy = _u(ang)
        pts = []
        for i in range(9):
            t = i / 8 - 0.5
            off = amp * math.sin(i * 1.9)
            pts.append((cx + px * width * t + ux * off, cy + py * width * t + uy * off))
        self.poly(pts, w)

    def arrow(self, x, y, ang=0, size=12, w=2):
        ux, uy = _u(ang)
        px, py = -uy, ux
        bx, by = x - ux * size, y - uy * size
        self.poly([(x, y), (bx + px * size * 0.4, by + py * size * 0.4),
                   (bx - px * size * 0.4, by - py * size * 0.4)], w, close=True, fill="#000000")

    def reducer(self, cx, cy, ang=0, w1=20, w2=10, length=18, w=2.4):
        ux, uy = _u(ang)
        px, py = -uy, ux
        a = (cx - ux * length / 2, cy - uy * length / 2)
        b = (cx + ux * length / 2, cy + uy * length / 2)
        self.poly([(a[0] + px * w1 / 2, a[1] + py * w1 / 2), (b[0] + px * w2 / 2, b[1] + py * w2 / 2),
                   (b[0] - px * w2 / 2, b[1] - py * w2 / 2), (a[0] - px * w1 / 2, a[1] - py * w1 / 2)], w, close=True)

    def nozzle(self, cx, cy_root, ang, bore, length, flange=True, w=2.8):
        ux, uy = _u(ang)
        px, py = -uy, ux
        ex, ey = cx + ux * length, cy_root + uy * length
        for sgn in (1, -1):
            self.line(cx + px * bore / 2 * sgn, cy_root + py * bore / 2 * sgn,
                      ex + px * bore / 2 * sgn, ey + py * bore / 2 * sgn, w)
        if flange:
            self.flange_face(ex, ey, ang, bore * 1.8, 3)
        return ex, ey

    def leader(self, x1, y1, x2, y2, w=1.6):
        self.line(x1, y1, x2, y2, w)

    # ---- SVG 输出（预览，受限子集）----
    def _svg_geom(self, e):
        k = e["kind"]
        if k == "line":
            d = f' stroke-dasharray="{e["dash"]}"' if e["dash"] else ""
            return (f'<line x1="{e["x1"]:.1f}" y1="{e["y1"]:.1f}" x2="{e["x2"]:.1f}" y2="{e["y2"]:.1f}" '
                    f'stroke-width="{e["w"]}"{d}/>')
        if k == "poly":
            d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in e["pts"]) + (" Z" if e["close"] else "")
            da = f' stroke-dasharray="{e["dash"]}"' if e["dash"] else ""
            f = f' fill="{e["fill"]}"' if e["fill"] else ""
            return f'<path d="{d}" stroke-width="{e["w"]}"{f}{da}/>'
        if k == "rect":
            return f'<rect x="{e["x"]:.1f}" y="{e["y"]:.1f}" width="{e["w"]:.1f}" height="{e["h"]:.1f}" stroke-width="{e["sw"]}"/>'
        if k == "path":
            f = f' fill="{e["fill"]}"' if e["fill"] else ""
            da = f' stroke-dasharray="{e["dash"]}"' if e["dash"] else ""
            return f'<path d="{e["d"]}" stroke-width="{e["w"]}"{f}{da}/>'
        if k == "arc":
            return (f'<path d="M {e["x0"]:.1f} {e["y0"]:.1f} A {e["rx"]:.1f} {e["ry"]:.1f} {e["rot"]} '
                    f'{e["laf"]} {e["sweep"]} {e["x1"]:.1f} {e["y1"]:.1f}" stroke-width="{e["w"]}"/>')
        if k == "ellipse":
            cx, cy, rx, ry = e["cx"], e["cy"], e["rx"], e["ry"]
            f = f' fill="{e["fill"]}"' if e["fill"] else ""
            return (f'<path d="M {cx-rx:.1f} {cy:.1f} A {rx:.1f} {ry:.1f} 0 1 0 {cx+rx:.1f} {cy:.1f} '
                    f'A {rx:.1f} {ry:.1f} 0 1 0 {cx-rx:.1f} {cy:.1f} Z" stroke-width="{e["w"]}"{f}/>')
        return ""

    def save_svg(self, path):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}">\n'
                f'  <rect x="0" y="0" width="{self.w}" height="{self.h}" fill="#ffffff" stroke="none"/>\n'
                f'  <g fill="none" stroke="#000000">\n')
        body = "\n".join("    " + self._svg_geom(e) for e in self.p)
        tl = []
        for e in self.t:
            tr = f' transform="rotate({e["rot"]:.1f} {e["x"]:.1f} {e["y"]:.1f})"' if e["rot"] else ""
            tl.append(f'<text x="{e["x"]:.1f}" y="{e["y"]:.1f}" font-size="{e["size"]}" '
                      f'text-anchor="{e["anchor"]}"{tr}>{e["s"]}</text>')
        tail = ('  </g>\n  <g fill="#000000" stroke="none" font-family="SimHei, Microsoft YaHei, sans-serif" '
                'font-size="28" text-anchor="middle">\n' + "\n".join("    " + t for t in tl) + '\n  </g>\n</svg>\n')
        with open(path, "w", encoding="utf-8") as f:
            f.write(head + body + "\n" + tail)
        return path

    # 兼容旧接口
    def save(self, path):
        return self.save_svg(path)

    # ---- DXF 输出（原生实体，同源直出）----
    def save_dxf(self, path, version="R2018"):
        if not _HAS_EZDXF:
            raise RuntimeError("save_dxf 需要 ezdxf")
        import os
        H = self.h
        doc = ezdxf.new(version, setup=True)
        msp = doc.modelspace()
        for name, color, lw in (("CONTOUR", 7, 0.35), ("DETAIL", 7, 0.18),
                                ("CENTER", 3, 0.13), ("TEXT", 7, 0.20)):
            doc.layers.add(name, color=color, lineweight=int(lw * 100))
            if name == "CENTER":
                doc.layers.get("CENTER").dxf.linetype = "CENTER"
        font_file = next((f for f in ("simhei.ttf", "msyh.ttf", "simsun.ttf")
                          if os.path.exists(os.path.join(r"C:\Windows\Fonts", f))), "simhei.ttf")
        fam = {"simhei.ttf": "SimHei", "msyh.ttf": "Microsoft YaHei", "simsun.ttf": "SimSun"}[font_file]
        st = doc.styles.add("CADHZ", font=font_file)
        st.set_extended_font_data(family=fam, italic=False, bold=False)
        doc.header["$TEXTSTYLE"] = "CADHZ"
        doc.header["$INSUNITS"] = 0
        ALIGN = {"start": TA.LEFT, "middle": TA.MIDDLE_CENTER, "end": TA.MIDDLE_RIGHT}

        def T(x, y):
            return (x, H - y)

        def layer_of(e):
            if e.get("dash"):
                return "CENTER"
            return "CONTOUR" if float(e.get("w", e.get("sw", 1))) >= 3.2 else "DETAIL"

        def hatch(pts, layer):
            h = msp.add_hatch(color=256, dxfattribs={"layer": layer})
            h.paths.add_polyline_path(pts, is_closed=True)
            h.set_solid_fill(color=256)

        for e in self.p:
            k = e["kind"]
            lay = layer_of(e)
            if k == "line":
                msp.add_line(T(e["x1"], e["y1"]), T(e["x2"], e["y2"]), dxfattribs={"layer": lay})
            elif k == "poly":
                pts = [T(x, y) for x, y in e["pts"]]
                msp.add_lwpolyline(pts, close=e["close"], dxfattribs={"layer": lay})
                if e["fill"] and e["close"]:
                    hatch(pts, lay)
            elif k == "rect":
                x, y, w, h = e["x"], e["y"], e["w"], e["h"]
                pts = [T(x, y), T(x + w, y), T(x + w, y + h), T(x, y + h)]
                msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": lay})
            elif k == "ellipse":
                cx, cy, rx, ry = e["cx"], e["cy"], e["rx"], e["ry"]
                if abs(rx - ry) < 0.5:
                    msp.add_circle(T(cx, cy), rx, dxfattribs={"layer": lay})
                    if e["fill"]:
                        hatch([T(cx + rx * math.cos(t), cy + rx * math.sin(t))
                               for t in [i * math.pi / 16 for i in range(32)]], lay)
                else:
                    major = max(rx, ry)
                    axis = (major, 0, 0) if rx >= ry else (0, -major, 0)  # y 翻转
                    msp.add_ellipse(T(cx, cy), major_axis=axis, ratio=min(rx, ry) / major,
                                    dxfattribs={"layer": lay})
            elif k == "arc":
                cx, cy, th1, dth = arc_center(e["x0"], e["y0"], e["rx"], e["ry"],
                                              e["rot"], e["laf"], e["sweep"], e["x1"], e["y1"])
                rx, ry = e["rx"], e["ry"]
                if abs(rx - ry) < 0.5:
                    s, en = th1, th1 + dth
                    if dth < 0:
                        s, en = en, s
                    msp.add_arc(T(cx, cy), rx, math.degrees(-en), math.degrees(-s),
                                dxfattribs={"layer": lay})
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
                                    start_param=-ep, end_param=-sp, dxfattribs={"layer": lay})
            elif k == "path":
                from render_svg import path_segments
                for sub in path_segments(e["d"]):
                    if len(sub) > 1:
                        pts = [T(x, y) for x, y in sub]
                        closed = len(sub) > 2 and abs(sub[0][0] - sub[-1][0]) < 0.5 and abs(sub[0][1] - sub[-1][1]) < 0.5
                        msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": lay})
                        if e["fill"] and closed:
                            hatch(pts, lay)

        for e in self.t:
            align = ALIGN.get(e["anchor"], TA.LEFT)
            rot = e["rot"]
            if rot:
                align = TA.MIDDLE_CENTER
            txt = msp.add_text(e["s"], height=e["size"], rotation=rot,
                               dxfattribs={"layer": "TEXT", "style": "CADHZ"})
            txt.set_placement(T(e["x"], e["y"]), align=align)

        for ent in msp:
            ent.dxf.linetype = "BYLAYER"
            ent.dxf.color = 256
        doc.saveas(path)
        return len(msp)