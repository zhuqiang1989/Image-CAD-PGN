# 踩过的坑与修法（照做即可绕过）

## 目录
- [A. 环境与工具假设](#a-环境与工具假设)
- [B. 判读与画法的坑](#b-判读与画法的坑)
- [C. 量测与复核的坑](#c-量测与复核的坑)
- [D. DXF 中文字体与编码](#d-dxf-中文字体与编码)
- [E. 脚本内部小坑](#e-脚本内部小坑)
- [F. 管线脚本与构建链的坑（本轮新增）](#f-管线脚本与构建链的坑本轮新增)

## A. 环境与工具假设

| 坑 | 现象 | 结论/修法 |
|---|---|---|
| 照抄别处的工具名 `image_edit` / `FileBatchUpload` / `present_files` | 本机没有这些 MCP 工具，流程一步都跑不动 | 本技能不依赖任何生图/上传工具；出图用 `render_svg.py`，交付用 `present_files`（本机有），没有就报路径 |
| 想用浏览器 MCP 做 "HTML/SVG → 截图" | `file://` 被禁；导航 `http://127.0.0.1` 与 `data:` 均 30s 超时（同机 HTTP 服务 `Invoke-WebRequest` 却能 200） | **放弃浏览器截图路线**，直接 Pillow 光栅化 |
| 想调外部光栅化/矢量工具 | `magick / inkscape / rsvg-convert / resvg / cairosvg / wand / svglib / cv2 / scipy / matplotlib` 本机全无 | 别 `pip install`、别调外部程序；`render_svg.py` 自带 SVG 子集渲染 |
| 有 `networkx` 没 `scipy` | 连通域需要库 | 脚本已用 networkx；缺 networkx 时只影响量测，出图不受影响 |
| PowerShell 里 `python -c "..."` 含 `$`/引号 | 被 PowerShell 吞掉，报 SyntaxError（如 `$TEXTSTYLE`） | 复杂检查一律写成 `.py` 脚本文件跑（本技能已备好 `dxf_check.py` 等） |
| 写了带中文注释的 `.ps1` 批处理 | Windows PowerShell 5.1 按 ANSI 读**无 BOM 的 UTF-8**，中文注释变乱码，接着报 `The string is missing the terminator` 语法错误 | 配套 `.ps1` 一律 **ASCII-only**（英文提示语），或存成 UTF-8 **带 BOM**；`scripts\build.ps1` 已是 ASCII 版 |
| 控制台中文乱码 | 打印的中文显示成 `????` | `$env:PYTHONIOENCODING='utf-8'`；乱码只是显示问题，文件里是好的 |

## B. 判读与画法的坑

1. **1:1 描手绘** → 得到"抖动的假工程图"，且把误差当成设计（例：手绘封头实测深 ≈0.38D，实际是手抖+与法兰粘连，按标准椭圆应是 D/4）。
2. **照抄别人成品** → 继承别人的走样。本项目样例图与手绘本就冲突三处：安全阀横位（样例压到右封头交界外 vs 手绘在右舱内 0.862）、右下降管位置（样例 0.96 vs 手绘 0.82）、A1 分界线线型（样例点划线 vs 手绘实线）。**先定基准（默认以手绘原图为准），再执行。**
3. **接管画进主体内侧**：法兰落在 `封头弧 x` 与 `交界 x` 之间 = 方向反了。必须用行探针判定（见 `checklist.md`），肉眼在缩略图上看不出来。
4. **臆造构件**：擅自加竖直中心线、人孔引出线、下降管法兰盘、把短管画成 200px 长支座。原图没有就别加；原图有的（如人孔引线）别删。
5. **符号统一化**：把安全阀的斜线抹掉、两个阀画成一样。
6. **分界线方位丢**：左右舱那条线一上一下、右舱那条画到封头内壁——都是原图信息，别抹平。
7. **文字**：错字/漏字/自造标签；编号不落在对应线上。逐字抄录 + 方位对应。
8. 参数没写出来的判断（"我觉得封头该这样"）→ 用户无法一句话纠正。**把判断写进参数并在回复里说明**。
9. **网格纸/坐标纸背景**：格子线会被探针/连通域当成主体，量测必失真。这类图**靠视觉判读主体**，忽略网格、图幅分区字母(D/E/F/2F)、涂改疙瘩、杂色笔误，只画设备/管线本体。
10. **不可识别文字**：潦草认不出的字**直接忽略**，不臆造、不追问、不留占位；可识别的逐字保留。旧版"问用户"已改为"忽略"。
11. **管板/内部波浪线**：手绘的竖直波浪双线判为管板，规整成直双线，不描波浪；内部虚线+端点圆判为隐藏管束，用 `hidden`+`circle`。

## C. 量测与复核的坑

1. **只目测不探针**：方向性错误漏检（本项目翻车点）。
2. **信了自动量测的"直段长"**：弧与母线相切处仍在容差内 → 每侧多算约 80px。真值取交界竖线的列位置。
3. **信了"尖点/外伸量"**：与轮廓连通的人孔法兰、点划线会被算进包围盒。真值用行探针。
4. **照片阈值**：Otsu 对马克笔过严（阈值 145 时母线都检不出）；改用 `thr=190~210` + `--dil 2`；`measure_lineart.py` 的行覆盖率阈值对照片常不触发，优先 `component_geom.py`。
5. **照片透视/纸面倾斜**：同一根线在不同 y 上漂 ±20px；归一化后取整数比（0.491→0.49），别把噪声写进参数。
6. **交付前没读成品图**：`present` 之前必须真看过一遍。

## D. DXF 中文字体与编码

**症状：CAD（中望/AutoCAD）打开 DXF，中文全是 `?`，英文数字正常。**

- 根因：**文字样式的字体不带 CJK 字形**。ezdxf 默认 `Standard` 样式指向 `txt.shx`（只有 ASCII）→ CJK 无字形 → 替换成 `?`。
- 不是编码问题：英文与中文的位置、字号都正常，说明字符串已正确解码。
- 修法（`svg2dxf.py` 已内置）：建一个 TTF 样式并全局指向它。核对 DXF 里的 STYLE 记录，应当长这样（与 AutoCAD 自存格式一致）：

  ```
  STYLE  2=CADHZ   3=simhei.ttf   4=(空 bigfont)
         1001=ACAD  1000=SimHei(家族名)  1071=34(TTF 标志)
  $TEXTSTYLE = CADHZ        全部 TEXT 的 style = CADHZ
  ```

- 复核：`python scripts\dxf_check.py x.dxf` → 应看到 `$TEXTSTYLE=CADHZ`、样式字体 `simhei.ttf`、"中文标注字体可用性: OK"。
- 兜底（个别年份的中望仍显示 `?`）：在 CAD 里 `STYLE` → 选 `CADHZ` → 字体名选"黑体(SimHei)" → `REGEN`。一步生效，不用重导。
- 彻底不依赖字体：把文字炸成多段线轮廓（显示一致，代价是不可编辑）。

**编码方面别再折腾**：

- ezdxf **无论怎么设都按 UTF-8 写 DXF**：设 `$DWGCODEPAGE=ANSI_936` 或 `doc.encoding="cp936"` 后，字节级检查仍是 UTF-8（GBK 解不开），且 `$DWGCODEPAGE` 并不会被保留。
- 所以**不要做"GBK 版 DXF"**（曾生成过一个自称 GBK 的 R2010 文件，实为 UTF-8，已废弃）。
- 要真 GBK/DWG：在 CAD 里 `DWGOUT`/`DXFOUT` 另存。
- 检查编码用 `python scripts\dxf_encoding.py x.dxf`（报告 UTF-8/GBK 可读性、`\U+` 转义、非 ASCII 字节数）。

## E. 脚本内部小坑

- `render_svg.py` 只吃 `references/svg-subset.md` 那个子集；写 `circle/ellipse/C/S/T/transform/<style>` 会**静默丢图**。
- 参数化生成器里文字与图形共用输出列表时，要把 `<text>` 行从图形 `<g>` 里剔出去，否则被重复绘制（图形组里 stroke 生效会描边）。
- 连通域膨胀别用 `np.roll`：它首尾环绕，会把图幅左右两端误连成同一个连通域（曾导致包围盒虚胖 300px）。脚本里用的是零填充平移 `_shift`。
- `svg2dxf.py` 里 `doc.dxfversion = "AC1032"` 这类硬赋值会覆盖版本参数，别留；层线型属性名是 `dxf.linetype`（不是 `dxf.ltype`）；实体颜色 `BYLAYER` 要写整数 `256`；TEXT 对齐要传 `TextEntityAlignment` 枚举（没有 `BASE_LEFT`，用 `LEFT`）。

## F. 管线脚本与构建链的坑（本轮新增）

1. **单线图拐弯封闭 ≠ 两点连线**（反复翻车三次才定稿）：正确做法是把**两根管线各自延长到交点**成尖角（轴测直角拐弯），焊口点 W 只是交点之前管段上的标记。**错误做法**：在两个焊口点之间另拉一条连接段（会画出 zigzag），或让管线停在焊口点就敞口。把整条管线写成一个 `poly` 连续折线，拐点 = 相邻两段公共端点；W3/W4、W1/W2 都按此处理。
2. **PowerShell 变量名不区分大小写**：`$preview`（字符串）和开关参数 `$Preview` 是**同一个变量**，赋值字符串会覆盖开关，触发 `Cannot convert ... to SwitchParameter`。局部变量别与参数同名（改用 `$prevPath`）。
3. **ezdxf 版本 API 差异**：`Importer` 没有 `import_modelspace_entities()`，1.4.x 里是 `import_modelspace()`。调第三方库方法前先 `python -c "import inspect; print(inspect.signature(...))"` 或 `dir()` 确认，别凭记忆写。
4. **DXF 被 CAD 占用 → PermissionError**：用户在 CAD 里打开着 DXF 时 `doc.saveas` 报 `[Errno 13]`。若构建链不检查退出码，会出现 **PNG 已更新、DXF 还是旧版**的不同源事故。`build.ps1` 已在 `svg2dxf` 后检查 `$LASTEXITCODE`，失败立即 throw、**不清理 SVG**；遇到占用提示用户关闭 CAD 再重跑。每个 python 步骤后都要查退出码。
5. **cadkit 坐标展开**：`s.line(*W1, (725,447), 2.2)` 会把元组当成 x2 → `TypeError: tuple.__format__`。`line` 要四个标量：`s.line(W1[0], W1[1], 725, 447, 2.2)`；`s.line(*W2, *W1, 2.4)` 这种两个元组展开成四标量才是对的。
6. **文字旋转/白描边**：渲染器文字旋转用 `transform="rotate(a x y)"`（DXF 映射 TEXT rotation）；白描边用 Pillow 原生 `stroke_width`+`stroke_fill`，比逐像素循环画白字快一个量级。
7. **DXF 曲线用真实体**：`cadkit.save_dxf()` 与 `svg2dxf.py` 都已把整圆发 `CIRCLE`、椭圆封头发 `ELLIPSE`、单段弧发 `ARC`/`ELLIPSE`（不再折线近似）。端点法弧→中心参数换算用 `cadkit.arc_center()`；**DXF y 翻转 T(x,y)=(x,H-y) 后，弧/椭圆的起止角要取负**，否则弧画反。
8. **cadkit 圆/点内部存为 ellipse**：`circle()`/`dot()` 在图元列表里 `kind="ellipse"`（靠 `fill` 区分实心/空心）。`gen_from_json.py` 的 primitives 回放必须有 `ellipse` 分支，只写 `circle`/`dot` 分支会漏画所有圆和焊口点。
9. **dxf_preview 的 ezdxf 细节**：`disassemble.make_primitive()` 得到的 `prim.vertices` 可能是**方法**不是属性，要 `callable()` 判断后再调用；`TEXT.get_placement()` 返回 `(枚举, Vec3)` 元组，取 `[1]` 才是坐标。本机无 matplotlib，预览用 Pillow 自绘 tessellate 顶点。
10. **JSON 解耦的坐标类型**：cadkit 图元里 `poly.pts` 是元组列表，`json.dump` 会转成数组（list），回放时 `tuple(p)` 还原即可，不必担心。高层 schema（vessel/isometric）字段缺省值要与范例硬编码值一致，否则出图与样例对不上。
