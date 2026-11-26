---
name: sketch-to-cad-vector
description: 把手绘/画图板绘制的工业管道图按工程规矩重绘为 CAD 风格二维线稿，同时输出高清 PNG 与可编辑 DXF。适用三类：压力容器示意图（卧式/立式筒体、封头、接管、人孔、隔板）、压力管道单线图（轴测管线、焊口 W/J 编号、阀门、放空点、规格标注、指北针）、管件与接管（弯头、三通、大小头、法兰、折断线）。不依赖生图模型，全部几何由代码给出：读图判语义 →（可选落成结构化 JSON）→ cadkit 同源直出 SVG 预览 + 原生实体 DXF（CIRCLE/ELLIPSE/ARC）→ Pillow 光栅化 PNG → 叠比对自检。当用户要求"手绘转 CAD""草图画成工程图""出可编辑 DXF/DWG""管道单线图重画""接管方向画反了""按比例重画""批量转 CAD"时使用。与 sketch-to-cad-lineart（生图模型版）互补：要矢量输出、标注零错字、比例可控时用本技能。
---

# 手绘工业管道图 → CAD 矢量线稿（代码绘制版）

## 核心信条

**先判读语义，再按制图规矩画；不要 1:1 描手绘的线。** 手绘线不直、弧不圆、比例被手抖带偏，照描像素会得到"抖动的假工程图"。正确做法是把图**读成一套工程对象**，用归一化参数描述，再用代码按规矩画准。

产出两件同源交付物，改一次参数全部同步：

| 产物 | 用途 |
|---|---|
| `*.png` | 交付位图，与原图同宽高比，标注为真字（SimHei） |
| `*.dxf` | 可编辑矢量：分层 CONTOUR/DETAIL/CENTER/TEXT，CENTER 点划线，TTF 中文样式；圆/椭圆/弧为**原生实体** CIRCLE/ELLIPSE/ARC |

cadkit 内部维护一份图元列表，**同源直出 SVG（预览）与 DXF（原生实体）**，两者几何完全一致；SVG 仅作预览/光栅化源，**任务完成后删除**（见交付）。全流程只用 Python + Pillow + ezdxf + networkx，不需要浏览器/外部光栅化/生图 API。

## 适用范围（先判类型）

只处理**手绘或画图板绘制的工业管道图**，三类：

1. **压力容器示意图**：筒体+封头+接管+人孔+隔板+液位线。范例 `scripts/gen_container.py`。
2. **压力管道单线图（轴测）**：管线沿轴测方向走，带焊口编号(W/J)、阀门、放空点、规格标注、指北针、表头表尾。范例 `scripts/gen_isometric.py`。
3. **管件/接管/常见部件**：弯头、三通、大小头、法兰、折断线等。直接用 `scripts/cadkit.py` 原语拼。

照片级杂乱手稿只要一张观感图 → 用生图模型版 `sketch-to-cad-lineart`。非工业管道图（建筑、机械零件照片等）不在本技能范围。

## 读图规则（最重要，占一半功夫）

**抓主体，忽略一切与主图无关的内容：**

- **忽略**：背景网格/坐标纸格子、图幅分区字母(D/E/F/2F)、杂色笔误、涂改疙瘩、纸张边缘阴影、手指、与主体无关的散点。这些一律不画。
- **保留主体**：设备轮廓、接管、符号、内部结构、中心线，以及它们之间的连接关系。
- **文字取舍**：能识别的文字**逐字保留**（含中文标签、编号、规格）；**识别不了的文字直接忽略**——不臆造、不追问、不留占位。编号要落在它原本依附的线上。
- **规整化**：直线只留给母线/接管/隔板/管线；曲线只给封头/弯头。手绘的抖一律不保留。封头按判读出的**形式**取标准几何（标准椭圆 2:1 → 深=D/4），不描手绘鼓肚。
- **转弯必须封闭**（单线图硬要求）：轴测管线每个转弯处，把**两根直线各自延长到交点**形成尖角（轴测上呈直角拐弯），即使用户原图转角断开留缝也要补到相交。**不是在两个焊口点之间另拉一条连接线**——焊口点只是管段上的标记，管线本身要延长相交成封闭折角。整条管线画成一条 `poly` 连续折线，拐点就是相邻两段的公共端点。
- **示意级即可**：处理对象是简易示意图，不是标准施工图——**只需还原主体轮廓和主要文字**，不必抠每一处细节。焊口点实心/空心皆可。拿不准的次要细节从简，别过度工程化。
- **不臆造**：原图没有的竖直中心线、引线、法兰盘、支座别加；原图有的别删。符号保持原图差异（安全阀带斜线、闸阀不带），不统一化。

判读问句、三类图的语义对照表、归一化取法见 `references/read-judgement.md`。

## 快速路径（默认走这条，提效）

判读稳定后，一张图只需三步：

1. **读图**：用视觉直接判读主体与文字，写成归一化参数（不必逐像素量测）。
2. **写脚本或 JSON**：抄改对应范例，或用 `cadkit.py` 原语写短脚本；也可把判读结论落成结构化 JSON（schema 见 `references/semantic-json.md`，示例在 `examples/`），用 `gen_from_json.py` 消费——改判读只改 JSON，不碰绘制代码。
3. **一条命令出图并清理**：

```powershell
pwsh -File <skill>\scripts\build.ps1 -Svg D:\out\draw.svg -Script D:\out\gen_x.py -Clean
# 容器范例： -Gen （可加 -HeadRatio 0.35 换封头）
# 已有 SVG： 省略 -Gen/-Script
# JSON 路线：python gen_from_json.py spec.json out.svg --dxf out.dxf  （cadkit 同源直出，DXF 原生实体）
```

`build.ps1` 一次完成 生成→PNG→DXF→字体复查；`-Clean` 删除 SVG/preview/`__pycache__`，**最终只剩 png+dxf**。cadkit 脚本也可在 `build()` 里直接 `s.save_dxf(path)` 同源出 DXF（弧/圆/文字皆原生实体），与 `svg2dxf` 解析路线等效。

**量测与探针是兜底，不是必经步骤**：干净图或比例一眼可判时跳过；只在比例拿不准、或要确认接管朝外/朝内时才用 `probe.py`/`component_geom.py`（加 `-Measure` 或单独跑，配方见 `references/checklist.md`）。容器封头接管方向这类肉眼难辨的错误，仍建议行探针复核一次。

## 批量处理（多张图）

批量时**先让用户做三个选择**（用 `interaction_ask`，一次问清）：

1. **输入文件夹**：存放待处理图片的目录。
2. **输出文件夹**：成品 png+dxf 的落点。
3. **DXF 方式**：每张图各出一个 DXF（分开），还是全部合并到一个 DXF（统一）。

然后逐张处理：读图判语义 → 用 cadkit/范例写一个 gen 脚本输出 SVG 到工作目录 → 全部读完后用 `batch.ps1` 一次构建：

```powershell
# 分开：每张图各出 png+dxf
pwsh -File <skill>\scripts\batch.ps1 -SvgDir D:\work\svg -OutDir D:\out
# 统一： additionally 合并成一个 merged.dxf（网格错开，互不重叠）
pwsh -File <skill>\scripts\batch.ps1 -SvgDir D:\work\svg -OutDir D:\out -Merge -Cols 2
```

`batch.ps1` 渲染全部 SVG→PNG+DXF，`-Merge` 调 `merge_dxf.py` 合并（保留各图图层与 CADHZ 中文样式），完成后删除源 SVG/`__pycache__`，输出目录只剩 png+dxf（统一模式多一个 merged.dxf）。读图仍是逐张由模型判读，脚本只负责出图与合并。

## 前置检查（开工前一次）

```powershell
python -c "import PIL, ezdxf, networkx, numpy; print('deps ok')"
python -c "import os; print(os.path.exists(r'C:\Windows\Fonts\simhei.ttf'))"
```

`simhei.ttf` 必须存在（PNG 中文与 DXF 中文样式都用它）。缺 networkx 只影响量测，不影响出图。

## 绘图要点

- **cadkit 原语**（`scripts/cadkit.py`）：`line/poly/rect/arc/ellipse/circle/dot`（焊口实心点）、`centerline/hidden`（点划线/虚线）、`text(...,rot=)`（rot 沿管线旋转规格标注）、`valve`（对顶三角+可选法兰标记/手轮）、`flange_marks/flange_face`、`breakline`（波浪折断线）、`arrow`（实心流向箭头）、`reducer`（大小头）、`nozzle`（接管+法兰面）、`leader`。坐标用画布像素，角度 0=右、90=下。
- **线型分层**（硬要求）：外轮廓粗实线 4；接管/剖切可见线 2.6–3；内部细实线 2.2；中心线细点划线 `34 9 6 9`（DXF 落 CENTER 层绿色点划线）；隐藏结构虚线 `12 7`。纯白底黑线，无阴影。
- **SVG 子集**：渲染器只吃 `svg/g/rect/line/polyline/polygon/path(M L H V A Q Z)/text`，没有 circle/ellipse（cadkit 用两段 A 弧拼）、没有 C/S/T/transform（文字旋转除外）。写超范围标签会静默丢图。详见 `references/svg-subset.md`。
- **参数化**：横向用"占直段长比例"、竖向用"占 D 比例"，坐标一律推导，改比例只动一行。

## 交付（只留 png+dxf）

1. 出图后**自己真读一遍 PNG** 再交付。
2. **视觉自检**：`python dxf_preview.py out.dxf preview.png` 渲染 DXF 核对几何（弧/圆/拐点/旋转标注）；`python compare.py 原图.png 成品.png overlay.png --side side.png` 叠比对核对主体/部件落位/文字。示意图不要求像素对齐，看拓扑与落位是否吻合、有无漏画错画。
3. 用 `-Clean` 跑最终构建，确认目录里只剩 `.png` 与 `.dxf`（SVG/preview/`__pycache__` 已删）。
4. 按当前环境的交付规则把 PNG 与 DXF 交给用户。
5. 回复写清：保留了哪些结构与标注、**忽略了哪些不可识别文字/背景**、做了哪些归位修正（封头形式、接管方向、折断线判定、转弯封闭）、比例由哪个参数控制。别暴露脚本内部细节。

## 已知边界与坑（务必读 `references/pitfalls.md`）

- **网格纸手绘**：背景格子会让探针/连通域量测失效（格子线占满图）——这类图**靠视觉判读**，别跑自动量测去"找母线"。
- 本机没有 ImageMagick/Inkscape/cairosvg/cv2/scipy/matplotlib → 别调外部光栅化、别指望 pip 现装。
- ezdxf **一律按 UTF-8 写 DXF**，做不出 GBK 版；要 GBK/DWG 在 CAD 里另存。
- DXF 中文变 `?` = 文字样式落在 txt.shx，**不是编码问题**；修法是 TTF 样式（脚本已内置 CADHZ→simhei.ttf）。
- 渲染器自实现，写超子集标签静默丢图；文字与图形分组输出，避免重复描边。
- 连通域膨胀别用 `np.roll`（首尾环绕误连），脚本用零填充平移。

## 已实现的增强（本轮升级）

- **同源直出**：`cadkit.py` 维护图元列表，`save_svg()` 出预览、`save_dxf()` 直发原生实体，两者几何一致，DXF 不再靠解析 SVG。`svg2dxf.py` 解析路线也同步升级（整圆→CIRCLE、单弧→ELLIPSE/ARC）。
- **原生曲线实体**：圆 `CIRCLE`、椭圆封头 `ELLIPSE`、单段弧 `ARC`/`ELLIPSE`（端点法弧→中心参数换算见 `cadkit.arc_center`，注意 DXF y 翻转后角度取负）。
- **读图/绘制解耦**：`gen_from_json.py` 消费结构化 JSON（`vessel`/`isometric` 高层 schema + `primitives` 通用回放），schema 见 `references/semantic-json.md`，示例 `examples/vessel_grid.json`、`examples/isometric_sheetA.json`。
- **视觉自检**：`dxf_preview.py` 把 DXF 渲染回 PNG（ezdxf disassemble + Pillow，不依赖 matplotlib）核对几何；`compare.py` 把原图淡化叠成品红线 + 左右并排，核对主体/部件落位/文字。

仍保留的边界：示意级重绘不追求像素级对齐（几何已归一化），叠比对用于确认拓扑与落位；不引外部转换器（Inkscape/ODA/LibreCAD 本机没有或工程语义差），ezdxf 直写最稳。

## 参考资源

- `references/read-judgement.md`：判读问句、三类图语义对照表、归一化取法、文字取舍与忽略规则。
- `references/checklist.md`：交付前质检清单 + 探针复核配方 + 清理确认。
- `references/svg-subset.md`：SVG 子集、线型规范、cadkit 符号画法速查。
- `references/semantic-json.md`：语义 JSON schema（vessel/isometric/primitives）与字段说明。
- `references/pitfalls.md`：环境/量测/DXF 中文字体/编码/网格背景/本轮新坑。
- `scripts/`：`build.ps1`（单图一条命令出图+清理）、`batch.ps1`（批量出图+可选合并）、`cadkit.py`（通用原语，同源 save_svg/save_dxf）、`gen_from_json.py`（语义 JSON 消费器）、`gen_container.py`（容器范例）、`gen_isometric.py`（单线图范例，转弯封闭）、`gen_vessel_sketch.py`（网格纸容器范例）、`merge_dxf.py`（多 DXF 合并）、`render_svg.py`/`svg2dxf.py`（出图/出 DXF）、`dxf_preview.py`（DXF→PNG 自检）、`compare.py`（原图叠比对）、`probe.py`/`component_geom.py`/`measure_lineart.py`（量测）、`dxf_check.py`/`dxf_encoding.py`（DXF 复查）。
- `examples/`：`vessel_grid.json`（高层容器 schema）、`isometric_sheetA.json`（primitives 回放）。
- `assets/`：三张测试输入（单线图 / 干净手绘容器 / 网格纸潦草容器）。`sample_out/`：对应成品（仅 png+dxf）。