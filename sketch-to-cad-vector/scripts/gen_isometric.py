#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_isometric.py — 压力管道单线图（轴测）→ CAD 线稿 SVG 示例生成器

判读结论（sheet_A_original.png，935×680）：
  · 表头三行：台账序号 261# / 管道编号 150-P3110-2T4 / 规格 D168/D89/D60*5.5/5.5/4.0。
  · 右上角指北针：上/北/东/西/南 五向箭头。
  · 左侧 D168 管段：折断线(管线出图,标 V3110) → 竖管(带法兰阀门) → 斜管(规格 D168×5.5,
    流向箭头) → 竖管 → 折线 → 竖管下行，经流向箭头接到主管汇合点 W6。
  · 主管汇合：左上 D60×4.0 斜管经 W8/W7 焊口对 → 小阀门 → W6/W5 焊口对(三通汇合点)。
  · 主斜管 D168×5.5 → 大小头 → D89×5.5，沿途三个放空点(竖短管+法兰阀门)，末端 W3/W4 焊口对。
  · 右支：W3 上行竖管(带大小头) → D60×4.0 斜管(流向箭头) → 竖管下行到 W1/W2 焊口对；
    W1 处一个放空点(斜短管+法兰阀门)。
  · 焊口对用圆圈圈起两个实心点，W=焊缝编号、J=口编号；规格标注沿管线方向旋转。
  · 表尾：辅助信息填写 ①所属区域 精制装置 ②所属装置 1层。

用法：python gen_isometric.py <out.svg>
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cadkit import SVG  # noqa: E402

W, H = 935, 680


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def ang_of(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def build():
    s = SVG(W, H)

    # ---- 表头 ----
    s.text(35, 24, "台账序号：261#", 19, "start")
    s.text(35, 49, "管道编号：150-P3110-2T4", 19, "start")
    s.text(35, 72, "规　格：D168/D89/D60*5.5/5.5/4.0", 19, "start")

    # ---- 指北针 ----
    cx, cy = 832, 72
    for ang, lab, lx, ly in ((-90, "上", 832, 26), (-143, "北", 788, 44),
                             (-35, "东", 878, 44), (141, "西", 788, 104), (37, "南", 878, 104)):
        ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        tx, ty = cx + ux * 40, cy + uy * 40
        s.line(cx, cy, tx, ty, 1.8)
        s.arrow(tx, ty, ang, 9)
        s.text(lx, ly, lab, 17)

    # ---- 焊口节点（管线在这些点转弯/汇合，转弯处必须封闭）----
    W8 = (383, 437); W7 = (393, 447); W6 = (417, 453); W5 = (428, 463)
    # W3/W4 是管段上的焊口点；斜管与竖管延长相交于拐点 C，形成封闭直角拐弯（轴测）
    C = (633, 577)                 # 斜管(D89)与右支竖管的交点 = 拐弯尖角
    W3 = (633, 558)                # 竖管上、C 上方
    W4 = (617, 568)                # 斜管上、C 左上方
    # W1/W2 同理：右支竖管与放空斜管延长相交于拐点 C2
    C2 = (784, 486)
    W2 = (784, 471)                # 竖管上、C2 上方
    W1 = (770, 477)                # 放空斜管上、C2 左上方

    # ---- 左侧 D168 管段：一条连续折线，转弯封闭，下行接到汇合点 W6 ----
    left_run = [(176, 362), (222, 335), (222, 185), (310, 136),
                (310, 285), (375, 196), (417, 174), W6]
    s.poly(left_run, 2.4)
    s.breakline(176, 362, -30, 20)
    s.valve(222, 277, 90, bw=20, bh=18, flanged=True)
    s.text(262, 148, "D168×5.5", 17, rot=-30)
    s.arrow(250, 167, 151, 11)
    s.arrow(417, 327, -90, 11)
    s.text(160, 390, "V3110", 18)

    # ---- 主管：D60→W8/W7→阀→W6/W5→D168/D89 斜管到拐点 C→竖管上行→右支，连续封闭 ----
    main_run = [(268, 388), W8, W7, W6, W5, C, (633, 397), (782, 311), C2]
    s.poly(main_run, 2.4)
    s.valve(405, 450, 24, bw=16, bh=14)          # W7-W6 间小阀门
    s.text(322, 404, "D60×4.0", 17, rot=ang_of((268, 388), W8))
    s.circle(388, 442, 24, 2.2); s.dot(*W8, 5); s.dot(*W7, 5)
    s.circle(422, 458, 24, 2.2); s.dot(*W6, 5); s.dot(*W5, 5)
    s.text(375, 412, "W8", 16); s.text(362, 456, "W7", 16); s.text(342, 466, "J4", 16)
    s.text(436, 432, "W6", 16); s.text(430, 486, "W5", 16); s.text(392, 494, "J3", 16)

    # ---- W5-C 主斜管上的三个放空点 + 大小头 + 规格 ----
    main_ang = ang_of(W5, C)
    for t, labx, laby in ((0.12, 432, 360), (0.29, 475, 385), (0.48, 517, 412)):
        bx, by = lerp(W5, C, t)
        s.line(bx, by, bx, by - 52, 2.2)
        s.valve(bx, by - 58, 90, bw=16, bh=14, flanged=True)
        s.text(labx, laby, "放空点", 17)
    rx, ry = lerp(W5, C, 0.66)
    s.reducer(rx, ry, main_ang, 18, 10, 16)
    p1 = lerp(W5, C, 0.28); s.text(p1[0] + 6, p1[1] + 26, "D168×5.5", 17, rot=main_ang)
    p2 = lerp(W5, C, 0.55); s.text(p2[0], p2[1] + 34, "D89×5.5", 17, rot=main_ang)

    # ---- W3/W4 焊口对（圆圈套住两个点与拐点 C）----
    s.circle(625, 565, 27, 2.2); s.dot(*W3, 5); s.dot(*W4, 5)
    s.text(650, 550, "W3", 16); s.text(588, 582, "W4", 16); s.text(652, 590, "J2", 16)

    # ---- 右支：C 上行竖管(大小头) → D60 斜管 → W2，已在 main_run 中封闭 ----
    s.reducer(633, 515, -90, 18, 10, 16)
    s.text(700, 344, "D60×4.0", 17, rot=ang_of((633, 397), (782, 311)))
    s.arrow(685, 367, ang_of((782, 311), (633, 397)), 11)
    # W1/W2 焊口对：竖管与放空斜管已在 C2 相交封闭；圆圈套住两点与拐点
    s.circle(777, 478, 27, 2.2); s.dot(*W2, 5); s.dot(*W1, 5)
    s.text(800, 464, "W2", 16); s.text(742, 498, "W1", 16); s.text(802, 500, "J1", 16)
    # 放空斜管：从阀门经 W1 延伸到拐点 C2（与竖管相交）
    s.line(722, 445, C2[0], C2[1], 2.2)
    s.valve(720, 443, 34, bw=16, bh=14, flanged=True)
    s.text(695, 420, "放空点", 17)

    # ---- 表尾 ----
    s.text(50, 575, "辅助信息填写：", 19, "start")
    s.text(65, 602, "①所属区域：精制装置", 19, "start")
    s.text(50, 629, "②所属装置：1层", 19, "start")
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    a = ap.parse_args()
    build().save(a.out)
    print(f"已生成 {a.out}（压力管道单线图示例）")