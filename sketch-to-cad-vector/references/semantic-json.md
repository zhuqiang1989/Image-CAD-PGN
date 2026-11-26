# 语义 JSON schema（读图与绘制解耦）

判读阶段把结论写成结构化 JSON，绘制阶段由 `scripts/gen_from_json.py` 消费，调 cadkit 同源出 SVG+DXF。
**改判读只改 JSON，不碰绘制代码**；便于批量复核、一键改参数、版本 diff。

```powershell
python scripts\gen_from_json.py spec.json out.svg --dxf out.dxf
```

坐标一律画布像素，角度 0=右、90=下（与 cadkit 一致）。所有 type 都有 `canvas:[w,h]`，可选 `_reading` 写判读备注（不影响出图）。

## type: vessel（高层容器）

| 字段 | 说明 |
|---|---|
| `shell` | `top_big/bottom/top_small`（大筒顶/底/小筒顶 y）、`x_big_left/x_big_right/x_small_left/x_small_right`（左右 x）。底平齐、偏心锥段由这些值推导 |
| `heads` | `right_depth/left_depth`（封头鼓出深度，标准椭圆 2:1 取 D/4） |
| `centerlines` | `[[x1,y1,x2,y2],...]` 点划线 |
| `tubesheets_small/big` | 管板双竖线 x 列表（小筒/大筒） |
| `internals` | `[{x,y0,y1,r}]` 内部管束：虚线+两端小圆 |
| `circles` | `[{x,y,r,w?}]` 独立圆 |
| `nameplate` | `{rect:[x,y,w,h],x,y,text,size?}` 铭牌框+字 |
| `manholes` | `[{x,y,ang,bore?,len?,flange:[x,y,w,h]}]` 人孔（接管+法兰框） |
| `nozzles_top/bottom` | `[{x,root?,bore?,len?}]` 上/下接管（root 默认筒顶/底） |
| `labels` | `[{x,y,text,size?,anchor?}]` 文字 |
| `leaders` | `[[tx,ty,px,py],...]` 引线（文字端→指向点） |

示例：`examples/vessel_grid.json`（网格纸容器，与 `gen_vessel_sketch.py` 同几何）。

## type: isometric（高层单线图）

| 字段 | 说明 |
|---|---|
| `runs` | `[{points:[[x,y],...],w?}]` 连续管线折线。**转弯封闭**：拐点=相邻两段公共端点，整条管线一条 poly |
| `lines` | `[{pts:[x1,y1,x2,y2],w?}]` 独立直线（如放空斜管） |
| `weld_circles` | `[{cx,cy,r}]` 焊口圈（空心） |
| `welds` | `[{x,y,r?}]` 焊口实心点 |
| `valves` | `[{x,y,ang?,bw?,bh?,flanged?}]` 阀门 |
| `vents` | `[{base:[x,y],len?}]` 放空立管+顶部法兰阀 |
| `reducers` | `[{x,y,ang?,w1?,w2?,len?}]` 大小头 |
| `arrows` | `[{x,y,ang?,size?}]` 流向箭头 |
| `breaklines` | `[{x,y,ang?,width?}]` 折断线 |
| `labels` | `[{x,y,text,size?,anchor?,rot?}]` 文字（rot 沿管线旋转规格标注） |
| `compass` | `{center:[cx,cy],r?,arms:[{ang,lx,ly,label}]}` 指北针 |

## type: primitives（通用回放，任意类型兜底）

直接列 cadkit 图元，适合非标准图或从范例导出：

```json
{"type":"primitives","canvas":[935,680],
 "primitives":[
   {"kind":"line","x1":0,"y1":0,"x2":10,"y2":10,"w":2.6,"dash":null},
   {"kind":"poly","pts":[[0,0],[10,0],[10,10]],"w":2.6,"close":false,"fill":null},
   {"kind":"rect","x":0,"y":0,"w":10,"h":10,"sw":2.6},
   {"kind":"arc","x0":0,"y0":0,"rx":5,"ry":5,"x1":10,"y1":0,"sweep":0,"w":4},
   {"kind":"ellipse","cx":5,"cy":5,"rx":5,"ry":3,"w":2.6,"fill":null},
   {"kind":"circle","cx":5,"cy":5,"r":3,"w":2.6},
   {"kind":"dot","cx":5,"cy":5,"r":5}],
 "texts":[{"x":5,"y":5,"text":"标注","size":16,"anchor":"middle","rot":0}]}
```

`circle/dot` 在 cadkit 内部存为 `ellipse`（fill 区分实心），回放时 `ellipse` 分支已覆盖。
示例：`examples/isometric_sheetA.json`（由 `gen_isometric.build()` 的图元列表导出，66 图元）。

## 用法建议

- 标准容器/单线图 → 用高层 schema（vessel/isometric），字段少、语义清晰、易改。
- 异形或想精确复刻某范例 → 用 primitives，或 `python -c "import gen_x,json; s=gen_x.build(); json.dump(...)"` 导出图元列表。
- 批量：每张图一个 JSON，`gen_from_json.py` 逐个出 svg+dxf，再 `batch.ps1 -Merge` 合并。