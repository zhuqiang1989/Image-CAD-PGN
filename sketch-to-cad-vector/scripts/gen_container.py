#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_container.py — 分室卧式容器手绘图 → CAD 线稿 SVG（参数化生成器）

对这张手绘的理解（写进参数，而不是照描像素）：
  · 主体：卧式圆筒形容器，全剖侧视图；两端【标准椭圆封头】(2:1，封头深 = D/4)。
  · 中央【隔板】把容器分成左右两舱（原图 B2 落在隔板下端，故隔板通到底）。
  · 左右封头中心线上各一个【人孔】：接管轴线水平、穿过封头尖点朝【外】伸出，末端矩形法兰。
  · 顶部两根接管垂直上伸，各带法兰面：左侧为【闸阀/截止阀】符号（对顶三角+阀杆+手轮），
    右侧为【安全阀】符号（对顶三角+阀杆+手轮+斜线）；两符号形态不同，不统一处理。
  · 底部两根【下降管】从各舱底部竖直向下，末端用【波浪折断线】表示管线延伸出图（原图无法兰盘，
    所以不是支座）。
  · A1/A2 是两舱的【分界/液位线】：原图均为连续实线，左舱略高于中心线、右舱略低于中心线，
    右舱那条一直画到右封头内壁。
  · B1/B3 是两端【封头与筒体交界环焊缝】编号，B2 是【隔板】编号——原图在这三处都画了贯通竖线，保留。
  · 文字：阀门 / 安全阀 / 人孔×2 / 下降管×2 / A1 / A2 / B1 / B2 / B3，共 11 处，按原图方位落位。

所有横向位置用「占筒体直段长的比例」表达，取自手绘实测归一化值；竖向尺寸用「占直径 D 的比例」表达。
"""
import argparse
import math

P = dict(
    canvas=(1962, 1280),
    D=400.0,                 # 筒体内径（画图用），手绘实测 直段/直径 ≈ 2.0
    straight_ratio=2.0,      # 筒体直段长 = 2.0 D（手绘实测 1.98，取整）
    head_ratio=0.25,         # 标准椭圆封头 2:1 → 封头深 = D/4
    cx=981.0,                # 主体横向中心（画布中心）
    cy=620.0,                # 水平中心线高度
    divider_at=0.534,        # 隔板位置（占直段长，手绘实测）
    valve_at=0.491,          # 顶部阀门接管位置（手绘实测，紧贴隔板左侧）
    safvalve_at=0.862,       # 顶部安全阀接管位置（手绘实测，右舱内）
    down_left_at=0.202,      # 左下降管位置（手绘实测）
    down_right_at=0.821,     # 右下降管位置（手绘实测）
    a1_above=0.149,          # 左舱分界线在中心线上方 0.149 D
    a2_below=0.102,          # 右舱分界线在中心线下方 0.102 D
    mh_bore=0.150,           # 人孔接管内径
    mh_len=0.150,            # 人孔接管外露长度
    mh_flange_od=0.240,      # 人孔法兰外径
    mh_flange_t=0.055,       # 人孔法兰厚度
    nozzle_bore=0.055,       # 顶部接管内径
    nozzle_len=0.095,        # 顶部接管伸出筒体长度
    down_bore=0.157,         # 下降管外径
    down_len=0.200,          # 下降管画出长度
    bowtie_w=0.115,          # 阀门符号宽度
    bowtie_h=0.105,          # 阀门符号高度（单个三角形高度一半的 2 倍）
    stem=0.185,              # 阀杆高度
    handle=0.085,            # 手轮宽度
)

OUT = []


def line(x1, y1, x2, y2, w, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    OUT.append(f'    <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
               f'stroke-width="{w}"{d}/>')


def poly(pts, w, close=False):
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts) + (" Z" if close else "")
    OUT.append(f'    <path d="{d}" stroke-width="{w}"/>')


def rect(x, y, w_, h_, sw):
    OUT.append(f'    <rect x="{x:.1f}" y="{y:.1f}" width="{w_:.1f}" height="{h_:.1f}" stroke-width="{sw}"/>')


def text(x, y, s, size=40, anchor="middle"):
    OUT.append(f'    <text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}">{s}</text>')


def build(p=P):
    D = p["D"]
    L = D * p["straight_ratio"]
    hd = D * p["head_ratio"]
    cx, cy = p["cx"], p["cy"]
    xj_l, xj_r = cx - L / 2, cx + L / 2          # 筒体与封头交界
    tip_l, tip_r = xj_l - hd, xj_r + hd          # 封头尖点
    xdiv = xj_l + L * p["divider_at"]
    top, bot = cy - D / 2, cy + D / 2

    # 中心线（细点划线，横贯全图；原图无竖直中心线，故不加）
    line(tip_l - D * 0.45, cy, tip_r + D * 0.45, cy, 1.6, "34 9 6 9")

    # 筒体母线 + 封头（标准椭圆弧）
    line(xj_l, top, xj_r, top, 4)
    line(xj_l, bot, xj_r, bot, 4)
    OUT.append(f'    <path d="M {xj_l:.1f} {top:.1f} A {hd:.1f} {D/2:.1f} 0 0 0 {xj_l:.1f} {bot:.1f}" stroke-width="4"/>')
    OUT.append(f'    <path d="M {xj_r:.1f} {top:.1f} A {hd:.1f} {D/2:.1f} 0 0 1 {xj_r:.1f} {bot:.1f}" stroke-width="4"/>')

    # 贯通竖线：左交界 B1、隔板 B2（双线）、右交界 B3
    for x, w in ((xj_l, 2.6), (xj_r, 2.6)):
        line(x, top, x, bot, w)
    line(xdiv - 4, top, xdiv - 4, bot, 3)
    line(xdiv + 4, top, xdiv + 4, bot, 3)

    # 舱内分界线（原图为连续实线）
    y_a1 = cy - D * p["a1_above"]
    y_a2 = cy + D * p["a2_below"]
    line(xj_l, y_a1, xdiv - 4, y_a1, 2.2)
    # 右封头内壁在 y_a2 处的横坐标
    dx = hd * math.sqrt(max(0.0, 1 - ((y_a2 - cy) / (D / 2)) ** 2))
    line(xdiv + 4, y_a2, xj_r + dx, y_a2, 2.2)

    # 人孔：接管轴线过封头尖点，水平朝外，末端法兰
    mb, ml, fod, ft = D * p["mh_bore"], D * p["mh_len"], D * p["mh_flange_od"], D * p["mh_flange_t"]
    for sgn, tip in ((-1, tip_l), (1, tip_r)):
        inner = tip + sgn * 6                      # 接管根部略微伸入封头，保证相接
        outer = tip + sgn * ml
        line(min(inner, outer), cy - mb / 2, max(inner, outer), cy - mb / 2, 2.8)
        line(min(inner, outer), cy + mb / 2, max(inner, outer), cy + mb / 2, 2.8)
        rect(outer - ft if sgn < 0 else outer, cy - fod / 2, ft, fod, 3)
        # 引出线（原图有）：从法兰外端面斜引到文字
        lx = outer - ft if sgn < 0 else outer + ft
        line(lx, cy, lx + sgn * D * 0.13, cy - D * 0.06, 1.6)

    # 顶部接管 + 阀门 / 安全阀符号
    nb, nl = D * p["nozzle_bore"], D * p["nozzle_len"]
    bw, bh, stm, hd_w = D * p["bowtie_w"], D * p["bowtie_h"], D * p["stem"], D * p["handle"]
    for at, label, slash in ((p["valve_at"], "阀门", False), (p["safvalve_at"], "安全阀", True)):
        c = xj_l + L * at
        line(c - nb / 2, top, c - nb / 2, top - nl, 2.8)
        line(c + nb / 2, top, c + nb / 2, top - nl, 2.8)
        line(c - nb, top - nl, c + nb, top - nl, 3)          # 接管端部法兰面
        wy = top - nl - bh / 2                               # 阀符号腰点
        poly([(c, wy), (c - bw / 2, wy - bh / 2), (c + bw / 2, wy - bh / 2)], 2.8, close=True)
        poly([(c, wy), (c - bw / 2, wy + bh / 2), (c + bw / 2, wy + bh / 2)], 2.8, close=True)
        line(c, wy, c, wy - stm, 2.4)
        line(c - hd_w / 2, wy - stm, c + hd_w / 2, wy - stm, 3.4)
        if slash:                                            # 安全阀的斜线标志
            line(c - bw / 2, wy + bh / 2 - 3, c + bw / 2, wy - bh / 2 + 3, 2.4)

    # 下降管（短管 + 波浪折断线，无法兰盘）
    db, dl = D * p["down_bore"], D * p["down_len"]
    for at in (p["down_left_at"], p["down_right_at"]):
        c = xj_l + L * at
        line(c - db / 2, bot, c - db / 2, bot + dl, 2.8)
        line(c + db / 2, bot, c + db / 2, bot + dl, 2.8)
        yb = bot + dl - 6
        seg = [(c - db / 2 + db * i / 6, yb + (6 * math.sin(i * 2.2))) for i in range(7)]
        poly(seg, 2.2)

    # 标注文字（11 处，方位按原图）
    text(xj_l + L * p["valve_at"], top - nl - bh / 2 - stm - 26, "阀门")
    text(xj_l + L * p["safvalve_at"], top - nl - bh / 2 - stm - 26, "安全阀")
    text(tip_l - ml - ft - D * 0.19, cy + D * 0.045, "人孔", 36)
    text(tip_r + ml + ft + D * 0.19, cy + D * 0.045, "人孔", 36)
    text(xj_l + L * p["down_left_at"], bot + dl + 62, "下降管")
    text(xj_l + L * p["down_right_at"], bot + dl + 62, "下降管")
    text(xj_l + 20, top - 30, "B1", 38)
    text(xj_r - 18, top - 30, "B3", 38)
    text(xdiv, bot + 46, "B2", 38)
    text(xj_l + (xdiv - xj_l) * 0.52, y_a1 - 22, "A1", 38)
    text(xdiv + (xj_r - xdiv) * 0.45, y_a2 + 48, "A2", 38)

    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{p["canvas"][0]}" height="{p["canvas"][1]}" '
            f'viewBox="0 0 {p["canvas"][0]} {p["canvas"][1]}">\n'
            f'  <rect x="0" y="0" width="{p["canvas"][0]}" height="{p["canvas"][1]}" fill="#ffffff" stroke="none"/>\n'
            f'  <g fill="none" stroke="#000000">\n')
    body = "\n".join(OUT)
    tail = ('  </g>\n'
            f'  <g fill="#000000" stroke="none" font-family="SimHei, Microsoft YaHei, sans-serif" '
            f'font-size="40" text-anchor="middle">\n'
            + "\n".join(t for t in OUT if "<text" in t)
            + '\n  </g>\n</svg>\n')
    # 文字从图形组里移出：先清掉 OUT 里的 text 行，避免重复绘制
    lines = [l for l in body.split("\n") if "<text" not in l]
    return head + "\n".join(lines) + "\n" + tail


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--head-ratio", type=float, default=P["head_ratio"])
    ap.add_argument("--straight-ratio", type=float, default=P["straight_ratio"])
    a = ap.parse_args()
    p = dict(P)
    p["head_ratio"] = a.head_ratio
    p["straight_ratio"] = a.straight_ratio
    svg = build(p)
    open(a.out, "w", encoding="utf-8").write(svg)
    D, L, hd = p["D"], p["D"] * p["straight_ratio"], p["D"] * p["head_ratio"]
    print(f"已生成 {a.out}")
    print(f"  直径 D={D:.0f}  直段={L:.0f} (L/D={L/D:.2f})  封头深={hd:.0f}({p['head_ratio']:.2f}D)  "
          f"含封头总长={L+2*hd:.0f}  人孔外伸={D*p['mh_len']:.0f}+法兰{D*p['mh_flange_t']:.0f}")
