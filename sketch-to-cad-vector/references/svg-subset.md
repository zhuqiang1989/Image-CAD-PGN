# SVG 子集与 cadkit 画法速查（渲染器 + DXF 转换器共同支持）

`render_svg.py` 是自实现光栅化器，`svg2dxf.py` 读同一份 SVG 出 DXF。**只写下面这些**；超范围标签不报错，只静默丢图（写 `<circle>` 就什么都不出来）。优先用 `cadkit.py` 原语，它已封装好这些写法。

## 可用元素

```xml
<svg width height viewBox>
  <rect x y width height fill stroke/>            <!-- 背景 fill=#ffffff stroke=none -->
  <g fill="none" stroke="#000000" stroke-width stroke-dasharray>
    <line x1 y1 x2 y2 stroke-width [stroke-dasharray]/>
    <polyline points/> <polygon points/>
    <path d="M L H V A Q Z" [fill] [stroke-dasharray]/>
  </g>
  <g fill="#000000" stroke="none" font-family="SimHei,...">
    <text x y font-size text-anchor [transform="rotate(a x y)"]>标注</text>
  </g>
</svg>
```

- `path` 命令只支持 **M m L l H h V v A a Q q Z z**；贝塞尔只认二次 Q（无 C/S/T）。
- 没有 `circle`/`ellipse` → cadkit 用两段 A 弧拼整圆/椭圆。
- 没有 `style` 选择器、`transform`（**文字旋转 `rotate(a x y)` 除外**）、`<use>`。
- `text` 吃 `x y font-size text-anchor`，旋转用 `transform="rotate(a x y)"`（a 顺时针，y 向下）；DXF 里映射为 TEXT rotation。
- 实心填充：`path` 带 `fill="#000000"` 且闭合 → PNG 实心、DXF 落 SOLID hatch（焊口点/箭头）。

## 圆弧写法（最常错）

```xml
<!-- 左封头：母线端点向下画外侧半椭圆 rx=封头深 ry=D/2，sweep=0 -->
<path d="M 587 432 A 100 200 0 0 0 587 832"/>
<!-- 右封头：sweep=1 -->
<path d="M 1381 432 A 100 200 0 0 1 1381 832"/>
```

`A rx ry 轴旋转 large-arc sweep x y`；半椭圆用 `large-arc=0`+正确 sweep，别误用 1 让弧跑进筒体。整圆/椭圆用 cadkit `circle/ellipse`（两段 A 拼）。

## 线型规范（工程图习惯，也是 DXF 分层依据）

| 用途 | stroke-width | 其它 | DXF 层 |
|---|---|---|---|
| 外轮廓/母线/封头 | 4 | 粗实线 | CONTOUR |
| 接管/剖切可见线/法兰 | 2.6–3 | 实线 | CONTOUR(≥3.2)/DETAIL |
| 内部结构/次要线 | 2.2 | 细实线 | DETAIL |
| 对称中心线 | 1.6 | `34 9 6 9` 点划线 | CENTER |
| 隐藏结构/内部管束 | 2.2 | `12 7` 虚线 | DETAIL |
| 标注文字 | — | SimHei 字号按图 | TEXT |

DXF 判定：`stroke-width≥3.2→CONTOUR`，有 dasharray→CENTER，text→TEXT，其余 DETAIL。

## cadkit 符号速查（`from cadkit import SVG`）

```python
s = SVG(w, h)
s.line(x1,y1,x2,y2,w=2.6)          # 直线
s.arc(x0,y0,rx,ry,x1,y1,sweep=0)   # 封头弧
s.circle(cx,cy,r); s.dot(cx,cy,5)  # 空心圆 / 实心焊口点
s.centerline(x1,y1,x2,y2)          # 点划线中心线
s.hidden(x1,y1,x2,y2)              # 虚线隐藏结构
s.valve(cx,cy,ang=90,flanged=True) # 对顶三角阀，腰点在管线上，ang 沿管向
s.flange_marks(cx,cy,ang,gap=16)   # 双短划法兰标记
s.flange_face(cx,cy,ang,width=30)  # 接管末端法兰面横线
s.breakline(cx,cy,ang,width=24)    # 波浪折断线
s.arrow(x,y,ang,size=12)           # 实心流向箭头，尖端在(x,y)
s.reducer(cx,cy,ang,w1,w2,length)  # 大小头开口梯形
s.nozzle(cx,cy,ang,bore,length)    # 接管+法兰面
s.text(x,y,"标注",size=28,rot=30)  # rot 沿管线旋转
s.save("out.svg")
```

角度约定：0=+x(右)，90=+y(下)，顺时针为正。阀门 bowtie 轴沿 ang；法兰标记/手轮垂直于 ang。

## 文字规则

- 可识别标注逐字抄录，不改写/漏字/新增；不可识别的忽略。位置与原图对应，编号落依附线端。
- 文字不压线：渲染器自动加白描边让中心线/分界线在字下断开，**别自己加白矩形**。
- DXF 文字一律样式 CADHZ（TTF），高度=font-size，对齐按 text-anchor 映射；旋转文字用 MIDDLE_CENTER。

## 生成器写法建议

参数放最上面（横向占直段长比例、竖向占 D 比例），坐标一律推导。`gen_container.py`（容器）、`gen_isometric.py`（单线图）是完整可跑范例，直接抄改；其它部件用 cadkit 原语拼短脚本。