#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_vessel_sketch.py — 网格纸潦草手绘卧式容器 → CAD 线稿 SVG 示例（cadkit 用法）

判读结论（微信图片_2026-11-26_221758_151.png，876×415）：
  · 主体：卧式容器，**底平齐偏心锥段**连接左小筒体与右大筒体；两端标准椭圆封头。
    大筒体 D≈270（顶57/底327/中心192），直段 x345..715；小筒体 D≈177（顶150/底327），
    x135..240；锥段顶母线 (240,150)→(345,57)，底母线贯通。左封头深≈44、右封头深≈67（≈D/4）。
  · 两端封头中心线各一个人孔：J1(左,小筒体中心y238)、J2(右,大筒体中心y192)，朝外+法兰盘。
  · 接管：小筒体顶1根、底1根(H1)；大筒体顶4根、底3根。
  · 管板：小筒体内 x145/215 双竖线、大筒体右 x680/710 双竖线（手绘波浪规整为直双线）。
  · 内部管束：x387/425/460/650 四列虚线+两端小圆（隐藏结构）；另有一个开口圆(510,135)。
  · 铭牌：方框(507,175,50,37)+“铭牌”。中心线：横y192、竖x497（点划线）。
  · 保留文字：人孔/J1/J2/H1/H2/管板/铭牌/南。
  · **忽略**：背景网格、图幅分区字母(D/E/F/2F)、内腔与封头里的潦草涂写（认不出）、杂色笔误。

用法：python gen_vessel_sketch.py <out.svg>
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cadkit import SVG  # noqa: E402

W, H = 876, 415


def build():
    s = SVG(W, H)
    # 主体几何
    top_b, bot = 57.0, 327.0          # 大筒体母线
    top_s = 150.0                      # 小筒体顶母线（底平齐）
    xj_l, xj_r = 345.0, 715.0          # 大筒体直段交界
    xs_l, xs_r = 135.0, 240.0          # 小筒体直段交界
    cy_b, cy_s = 192.0, 238.5

    # 中心线
    s.centerline(40, cy_b, 840, cy_b)
    s.centerline(497, 15, 497, 400)

    # 大筒体母线 + 右封头
    s.line(xj_l, top_b, xj_r, top_b, 4)
    s.line(xs_l, bot, xj_r, bot, 4)
    s.arc(xj_r, top_b, 67, 135, xj_r, bot, sweep=1, w=4)
    # 小筒体母线 + 左封头 + 偏心锥段
    s.line(xs_l, top_s, xs_r, top_s, 4)
    s.arc(xs_l, top_s, 44, 88.5, xs_l, bot, sweep=0, w=4)
    s.line(xs_r, top_s, xj_l, top_b, 4)        # 锥段顶母线
    # 交界竖线
    for x, y0 in ((xs_l, top_s), (xs_r, top_s), (xj_l, top_b), (xj_r, top_b)):
        s.line(x, y0, x, bot, 2.6)

    # 管板（双竖线，规整化）
    for x in (145, 215):
        s.line(x - 3, top_s, x - 3, bot, 2.2)
        s.line(x + 3, top_s, x + 3, bot, 2.2)
    for x in (680, 710):
        s.line(x - 3, top_b, x - 3, bot, 2.2)
        s.line(x + 3, top_b, x + 3, bot, 2.2)

    # 内部管束（虚线+端点圆）
    for x in (387, 425, 460, 650):
        s.hidden(x, 87, x, 178)
        s.circle(x, 82, 5, 2.0)
        s.circle(x, 183, 5, 2.0)
    s.circle(510, 135, 8, 2.2)

    # 铭牌
    s.rect(507, 175, 50, 37, 2.2)
    s.text(532, 199, "铭牌", 16)

    # 人孔 J1（左，小筒体中心）/ J2（右，大筒体中心）
    s.nozzle(91, cy_s, 180, 28, 20, flange=False)
    s.rect(64, cy_s - 26, 7, 52, 2.8)
    s.nozzle(782, cy_b, 0, 28, 20, flange=False)
    s.rect(802, cy_b - 26, 7, 52, 2.8)
    s.text(40, 240, "人孔", 18)
    s.text(40, 268, "J1", 18)
    s.text(838, 190, "人孔", 18)
    s.text(838, 218, "J2", 18)

    # 顶部接管（T 形：两竖线+法兰面）
    s.nozzle(180, top_s, -90, 24, 23)
    for x in (405, 560, 612, 673):
        s.nozzle(x, top_b, -90, 22, 17)
    # 底部接管
    s.nozzle(190, bot, 90, 24, 23)
    for x in (535, 580, 670):
        s.nozzle(x, bot, 90, 22, 20)

    # 标注
    s.text(141, 372, "H1", 18)
    s.text(722, 362, "H2", 18)
    s.text(235, 108, "管板", 16)
    s.leader(235, 114, 215, 150)
    s.text(105, 393, "南", 18)
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    a = ap.parse_args()
    build().save(a.out)
    print(f"已生成 {a.out}（网格纸手绘容器示例，已忽略网格/涂改/不可识别文字）")