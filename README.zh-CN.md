# AI Paper Reading · AI 论文阅读

[English](README.md) | **简体中文**

**把一篇论文的故事线、模型框架和实验依据读明白。**

给 AI Agent 一个 PDF、arXiv 链接或论文名称，先准备好原文、图表与代码，再按需要选择：一次讲完的**概览**，或结合原图、公式和具体样例的**精读**。

[快速开始](#快速开始) · [两种阅读模式](#两种阅读模式) · [材料与目录](#材料与目录) · [致谢与许可](#致谢与许可)

## 两种阅读模式

| 模式 | 适合什么时候 | 讲什么 | 输出节奏 |
|---|---|---|---|
| **概览** | 第一次接触，先建立整体理解 | 基本情况、动机、故事线、模型框架 | 一次回复完整输出 |
| **精读** | 想真正理解方法和实验 | 动机 → 方法 → 训练 → 实验 | 默认分站推进，支持跳站或一次讲完 |

用户在开讲前给出的具体要求优先。只问某张图、某个公式或一段代码时，直接回答该问题；仅提供论文而未指明模式时，默认概览。

### 概览：先讲清为什么做、怎么做

从“研究什么问题、过去卡在哪里、作者的关键想法”开始，再展示论文原框架图，沿数据流解释各模块为什么存在、如何连接，最后串起一次输入到输出的过程。

重点是**故事线和模型框架**，不会默认展开所有公式，也不需要每讲一段都回复“继续”。

### 精读：四站走通一篇论文

```text
① 动机
   问题、已有方法的不足、作者的关键假设
      ↓
② 方法
   原框架图、模块设计目的、每个公式与符号
      ↓
③ 训练
   一条样本 → 数据处理 → 输入输出信息流 → 损失 → 参数更新
   再用具体例子，对照推理过程与官方代码
      ↓
④ 实验
   主实验、消融，以及论文实际提供的其他实验与局限
```

- **方法不止列模块。** 每项设计要对应它解决的问题，公式要解释符号、形状、运算和相互关系。
- **训练不止报配置。** 从一条样本出发，让输入、中间表示、预测、监督信号和更新过程连起来。
- **实验不止念数字。** 展示原表原图，解释比较条件、关键结果，以及这些结果支持多大的结论。
- **图表直接展示。** 先说明怎么读，再解释细节；密集图片可放大，表格可单独裁出。
- **不懂就换讲法。** 用具体数字、小尺寸例子、朴素方案对比与代码对照帮助理解。

## 快速开始

需要能读取文件、访问网络、执行 Python 并展示图片的 AI Agent。脚本依赖 **Python 3.9+** 和 **PyMuPDF**；阅读与讲解由 Agent 完成，脚本本身不会调用模型。

### 安装到 Codex

```bash
git clone https://github.com/Xielewei/ai-paper-reading.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/ai-paper-reading"

cd "${CODEX_HOME:-$HOME/.codex}/skills/ai-paper-reading"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

让 Agent 使用该目录下的 `.venv/bin/python` 运行材料脚本，或使用其他已安装 PyMuPDF 的 Python 环境。

### 安装到 Claude Code

```bash
git clone https://github.com/Xielewei/ai-paper-reading.git \
  ~/.claude/skills/ai-paper-reading

cd ~/.claude/skills/ai-paper-reading
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

其他 Agent 可以将仓库放在工作目录，并让它读取 [SKILL.md](SKILL.md)。图片展示方式由当前界面决定。

### 直接这样说

```text
用 $ai-paper-reading 概览这篇 PDF，重点讲故事线和模型框架。

帮我找到并下载这篇论文，放到“医学影像”领域下面，然后概览。

精读这篇论文，按照动机、方法、训练、实验来。

方法部分每个公式和符号都讲清楚，结合原框架图解释设计目的。

拿一条训练样本，把输入、输出和 loss 的计算走一遍。

单独展示表 2，解释主实验与消融分别说明了什么。

把刚才讨论的三个问题整理成笔记。
```

上面的 `$ai-paper-reading` 是 Codex 的显式调用写法；其他 Agent 使用其对应的 skill 调用方式。Skill 指令与参考示例目前以中文编写；可以在提示中指定希望使用的讲解语言。

## 材料与目录

默认论文库是 **`~/Desktop/paper/`**，按“领域 → 论文”两级归档：

```text
~/Desktop/paper/
└── 医学影像/
    └── <论文简称>_<年份>_MICCAI/
        ├── paper.pdf
        ├── source/              # 能获取到的 arXiv LaTeX 源码
        ├── paper.tex            # 展开后的正文，用于阅读与定位
        ├── paper.txt            # 按页提取的文本
        ├── outline.md           # 章节、公式位置索引
        ├── meta.json            # 标题、作者、日期、相关链接
        ├── figures/
        │   ├── fig-*.png
        │   ├── tab-*.png
        │   ├── index.md
        │   ├── index.json
        │   └── _contact.png     # 图表总览，便于检查裁剪
        └── code/                # 找到的官方代码，浅克隆
```

目录示例中的字段是占位说明，不代表一篇真实论文。

**命名规则：**优先使用论文明确给出的简称；没有简称而有小标题时用小标题，否则使用文章标题。随后加年份；已正式发表且能核实 venue 时，加会议或期刊简称，例如 MICCAI、CVPR、TMI。仅有预印本或尚未确认发表时，不猜测会议。

支持本地 PDF、PDF 直链、arXiv ID/链接和已有论文目录。也可以先让 Agent 按论文名称寻找原文。本地 PDF 保留原件；同一篇重复阅读复用已有目录。

### 笔记：你说记录，才记录

**默认不创建 `精读笔记.md`，不自动保存对话或逐站追加问答。**

只有明确说“整理成笔记”“记录这些问题”等，才按指定范围生成或更新。材料大纲和图表索引仍会自动准备，它们只用于检索定位。

`profile.md` 用来记录背景与讲解偏好；论文笔记与问答遵循上述按需规则。`profile.md` 已加入 Git 忽略列表。

### 直接运行材料脚本

在仓库根目录运行；名称、年份和 venue 应先由用户或 Agent 核实：

```bash
# 导入本地 PDF；没有正式 venue 时省略 --venue
.venv/bin/python scripts/fetch_paper.py "/path/to/paper.pdf" \
  --field "医学影像" --name "已核实的论文简称" --year 2025 --venue MICCAI

# 从 arXiv 准备材料；这是 π0 的预印本示例
.venv/bin/python scripts/fetch_paper.py 2410.24164 \
  --field "具身智能" --name "pi0" --year 2024

# 已有目录：补充缺失材料，重新生成文本、索引和自动图表
.venv/bin/python scripts/fetch_paper.py "$HOME/Desktop/paper/具身智能/pi0_2024"

# 未自动找到代码时，手动指定已确认的官方仓库
.venv/bin/python scripts/fetch_paper.py "$HOME/Desktop/paper/具身智能/pi0_2024" \
  --code https://github.com/Physical-Intelligence/openpi

# 从 PDF 的第 4 页裁出局部；坐标为 0–1 比例
.venv/bin/python scripts/crop.py "/path/to/paper.pdf" \
  --page 4 0.08 0.10 0.92 0.55 -o "/path/to/detail.png"
```

`--root` 修改论文库根目录，`--dest` 指定完整论文目录，`--no-clone` 只寻找代码链接而不克隆。字段、图表和下载选项可以用 `--help` 查看。

已有的用户图表不会混进自动裁图目录：若 `figures/` 里有用户整理的图，自动图表会放到 `figures-auto/`。原 PDF、源码和代码通常复用，文本与自动索引会重建；自己编辑过的自动产物应先另存。

## 文件导航

| 文件 | 用途 |
|---|---|
| [SKILL.md](SKILL.md) | Agent 执行的完整阅读流程 |
| [references/examples.md](references/examples.md) | 框架、数据、公式与代码走读的讲解示例 |
| [references/notes-template.md](references/notes-template.md) | 用户要求记录时才使用的笔记模板 |
| [profile.example.md](profile.example.md) | 背景、知识基础和举例偏好模板 |
| [scripts/fetch_paper.py](scripts/fetch_paper.py) | PDF、源码、元数据、代码与材料索引 |
| [scripts/extract_figures.py](scripts/extract_figures.py) | 自动提取图表及总览拼图 |
| [scripts/crop.py](scripts/crop.py) | 原图、表格、公式的局部裁剪 |

## 已知限制与验证

- 图表裁剪依赖 caption 与版式规则，复杂表格、跨栏图可能需要手动重裁。Agent 应在讲解前检查原图。
- 只有能获取源码的论文才有 `source/` 和 `paper.tex`；非 arXiv 或仅上传 PDF 的论文可能没有源码。
- 自动寻找代码依赖论文与项目页面的链接，可能漏检或误选，需要核实论文与实现的对应关系。
- 仓库代码默认只读，不替用户运行论文的训练脚本或安装其依赖。
- 不提供训练结果复现保证。材料准备成功也不代表论文结论已被验证。

材料流程已用合成 PDF 验证：本地导入、目录命名、源码展开、图表提取、局部裁剪、已有材料保护及不自动生成笔记。URL 下载和代码克隆分支使用模拟响应测试，尚未做真实网络下载的端到端验证。

运行同类检查：

```bash
.venv/bin/python tests/smoke_test.py
```

## 致谢与许可

感谢 [skJack/kelip-paper-reading](https://github.com/skJack/kelip-paper-reading) 提供的阅读流程、材料准备脚本与讲解示例，本项目在其基础上进行了定制。

使用 [MIT License](LICENSE)，保留原作者版权声明。
