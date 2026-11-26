# img2cad — --CAD-PGN

把手绘或画图板绘制的工业管道图按工程制图规矩重绘为 CAD 风格的二维线稿，同时输出高清 PNG 光栅图与可编辑的 DXF 矢量文件。不依赖任何 AI 生图模型，所有几何均由代码直接构造：先读图并判断语义，再按工程规范绘制，最后同源直出 SVG/DXF/PNG 三件套，并以叠比对完成视觉自检。

适用对象为三类工业图纸：**压力容器示意图**（卧式/立式筒体、封头、接管、人孔、隔板）、**压力管道单线图**（轴测管线、焊口 W/J 编号、阀门、放空点、规格标注、指北针）以及**管件与接管**（弯头、三通、大小头、法兰、折断线）。

---

## 功能概述

| 能力 | 说明 |
| --- | --- |
| **语义判读** | 忽略背景网格、坐标纸分区字母、杂色笔误、涂改疙瘩、纸张边缘阴影、手指及无关散点；保留设备轮廓、接管、符号、内部结构与连接关系；识别不了的文字直接忽略 |
| **工程规整化** | 直线留母线/接管/隔板/管线，曲线只给封头/弯头；转弯处将两根直线各自延长到交点形成尖角，不在焊口点之间拉线 |
| **同源直出** | SVG 预览与原生实体 DXF（CIRCLE/ELLIPSE/ARC）几何完全一致，再经 Pillow 光栅化为高清 PNG |
| **视觉自检** | `dxf_preview.py` 渲染预览、`compare.py` 与原图叠比对确认拓扑与落位 |
| **批量处理** | 支持逐张处理并一次构建，可分别导出各图的 png+dxf，也可合并到单一 merged.dxf 中保留图层与 CADHZ 中文样式 |

## 目录结构

```
D:\Deepseek\img2cad\
├── .gitignore                  # Git 忽略规则（Python 缓存、虚拟环境、OS 垃圾、构建产物）
├── README.md                   # 本仓库说明文档
└── sketch-to-cad-vector\       # 核心工作区
    ├── SKILL.md                # 技能说明：读图规则、三类图语义对照、归一化取法
    ├── assets\                 # 测试输入素材（容器图、单线图、手绘图等）
    ├── examples\               # 结构化示例（vessel_grid.json、isometric_sheetA.json）
    ├── references\             # 参考文献（read-judgement.md、semantic-json.md、checklist.md、pitfalls.md、svg-subset.md）
    └── scripts\                # 工具脚本集
        ├── build.ps1           # 单次出图命令入口
        ├── batch.ps1           # 批量构建入口
        ├── cadkit.py           # 绘图原语库（line/poly/rect/arc/ellipse/dot/text/valve/flange_marks/breakline/arrow/reducer/nozzle/leader）
        ├── gen_from_json.py    # 从 JSON 生成图形（读图/绘制解耦）
        ├── gen_container.py    # 容器类绘图脚本
        ├── gen_isometric.py    # 轴测管线脚本
        ├── gen_vessel_sketch.py# 压力容器示意图脚本
        ├── render_svg.py       # SVG 子集渲染器
        ├── svg2dxf.py          # SVG→DXF 转换
        ├── dxf_preview.py      # DXF 预览生成
        ├── compare.py          # 图像叠比对
        ├── merge_dxf.py        # 多图合并到单一 DXF
        ├── probe.py            # 环境探测
        ├── measure_lineart.py  # 线宽测量
        ├── dxf_check.py        # DXF 校验
        └── dxf_encoding.py     # 编码处理
```

> 注：`assets/examples/references/scripts/SKILL.md/README.md` 均为仓库核心内容，不会被 `.gitignore` 排除。

## 使用方式简介

### 前置检查

```powershell
python -c "import PIL, ezdxf, networkx, numpy; print('deps ok')"
python -c "import os; print(os.path.exists(r'C:\Windows\Fonts\simhei.ttf'))"
```

### 快速路径（三步）

1. **读图**：观察手绘图，提取主体几何与连接关系
2. **编写脚本或 JSON**：参考 `references/semantic-json.md` 中的 schema，以 `examples/vessel_grid.json`、`examples/isometric_sheetA.json` 为例
3. **一条命令出图并清理**：

```powershell
pwsh -File <skill>\scripts\build.ps1 -Svg D:\out\draw.svg -Script D:\out\gen_x.py -Clean
```

### 批量处理

1. 让用户选择三个参数：输入文件夹、输出文件夹、DXF 方式
2. 逐张处理后用 `batch.ps1` 一次性构建（每张图分别输出 png+dxf，或合并到 merged.dxf，保留各图图层与 CADHZ 中文样式）

### 交付要求

- 真读一遍 PNG 再交付
- 视觉自检：`python dxf_preview.py out.dxf preview.png` 与 `python compare.py 原图.png 成品.png overlay.png --side side.png`
- 使用 `-Clean` 确认目录只剩 png+dxf
- 回复需包含：保留项、忽略项、归位修正、比例来源

## 注意事项

- **网格纸手绘靠视觉判读**，不必追求像素级对齐，示意级即可
- **本机环境限制**：无 ImageMagick / Inkscape / cairosvg / cv2 / scipy / matplotlib，依赖自实现渲染器
- **DXF 编码**：ezdxf 一律 UTF-8 写入，做不出 GBK 版；DXF 中文文字样式落在 txt.shx 时，改用 TTF 样式（脚本内置 CADHZ → simhei.ttf）
- **渲染器限制**：只支持 svg/g/rect/line/polygon/path(M L H V A Q Z)/text 子集，超标签会静默丢图
- **连通域膨胀勿用 np.roll**
- **不臆造**：原图没有的中心线、引线、法兰盘、支座不要添加；原图有的不要删除
- **纯白底黑线**，无阴影，中心线细点划线 (34 9 6 9)，隐藏结构虚线 (12 7)
