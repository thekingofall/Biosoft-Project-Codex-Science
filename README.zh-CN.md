# Codex Science

[English](README.md) · **简体中文**

**把文献、数据、分析和论文写作接到同一个 Codex 工作流程里。**

Codex Science 是面向生物医学研究的 Codex 工具包。你描述研究问题，Codex 调用科研数据库、阅读本地论文、整理证据，继续编写分析代码、绘图和修改文章。结果保存在你的项目目录，可以检查、编辑和复用。

例如，你可以从“衰老过程中 T 细胞发生了哪些变化”开始：检索论文，比较研究对象和实验设计，建立带页码的证据表，再围绕自己的结果写出引言和讨论。手里有表达矩阵或候选基因时，也可以接着查询公开数据、运行分析并整理图件。

[文献与写作](#从读论文到写文章) · [数据与模型](#科研数据库与生物模型) · [使用示例](#试着这样问) · [安装](#安装) · [功能范围](docs/application-coverage.md)

## 从读论文到写文章

### 找到论文，保留可追溯的引用

通过 Crossref 查询论文和 DOI，通过数据库连接器访问 PubMed、arXiv、OpenAlex、bioRxiv 等来源。Codex 可以根据你的问题比较研究结果，整理已有共识、争议和证据缺口。参考文献支持导出为 **BibTeX、RIS 和 JSON**，方便交给写作软件继续使用。

Crossref 查询可以从基础工作台开始使用。其他来源根据各自要求配置邮箱或 API 密钥。引用所支持的具体结论，需要结合论文原文判断。

### 读 PDF，把证据留在原文旁边

读取目录和指定页面，搜索相关段落，提取 DOI、GEO 编号，并将页面渲染成图片查看图表。证据表保留研究问题、来源、页码、摘录、发现和局限；保存本地 PDF 摘录时，会检查引用文字是否出现在指定页面。

页面搜索采用文字匹配。扫描版论文可以交给 Codex 阅读页面图片或配合 OCR。处理长文档时，可以分批覆盖全文。

### 梳理论文主线，写成可以继续修改的稿件

让 Codex 结合摘要、结果和图注，检查文章的核心问题、各张图的作用、论证顺序以及还缺少的证据。可以继续起草或修改引言、结果、讨论和图注，也可以围绕疾病人群整理研究资料。

稿件保留为 Markdown，并可导出 **Word**。目前支持标题、段落、列表、表格、加粗、斜体、链接和本地图片；复杂公式保留原始文本。交付前可检查空章节、待补引文和缺失图件。

## 从数据到科研图

用现有 R、Python 或服务器环境处理自己的数据。内置 R 绘图工具可将整理好的 CSV 画成散点图、折线图、箱线图或柱状图，同时保存 **PDF、PNG、输入校验值和绘图参数**。使用英文标注、Arial 和统一配色。

多面板组图支持规则网格或 12 列布局，保留各面板比例，添加 Arial 面板字母，并输出 PDF、PNG 和来源记录。

更复杂的单细胞、富集和空间分析，由 Codex 结合相应软件与分析技能完成。分析脚本、绘图数据和图件保留在项目中，便于复跑和修改。

## 科研数据库与生物模型

数据库连接器提供基因、蛋白、通路、化合物、临床试验和公开组学数据的查询入口，涉及 Ensembl、UniProt、PubChem、GEO、ChEMBL 等服务。已有连接器保留 23 个领域的 224 项查询操作；服务配置和实际可用性随来源而定。

模型目录覆盖以下工作流，并提供输入格式、软件入口、权重要求和预期输出：

| 研究任务 | 模型与工具 |
|---|---|
| 结构预测与对接 | AlphaFold2、Boltz、Chai-1、DiffDock、ESMFold2、OpenFold3 |
| 蛋白质序列设计 | ProteinMPNN、LigandMPNN、SolubleMPNN |
| 序列与调控研究 | ESM2、Evo2、Borzoi |
| 单细胞建模 | scGPT、scvi-tools |

这些模型需要各自的环境、权重和计算资源。Codex Science 可以检查本机环境、准备 Bash/Slurm 作业、调用你配置的模型服务并记录结果文件。实际推理需要在选定环境中验证，当前版本尚未完成全部模型运行测试。

## 试着这样问

```text
$codex-science
检索 T 细胞衰老相关论文，按研究人群、实验方法和主要发现整理证据。
优先阅读原始研究，给出可以追溯到论文的引用，并导出 RIS。
```

```text
$codex-science
阅读项目里的三篇 PDF，比较它们如何处理批次效应。
把方法、适用条件、局限和原文页码整理成表格，再写一段方法比较。
```

```text
$codex-science
结合 manuscript.md 和 figures 里的图，梳理论文主线。
修改结果和讨论，检查缺失的引用与图件，然后导出 Word。
```

```text
$codex-science
检查我的计算环境是否适合运行 Boltz。
说明需要的输入和权重，准备运行脚本，等待算力配置后执行。
```

## 安装

需要 **Python 3.12、Codex 和可用的 MCP 支持**。R 绘图另外需要 R 与 `jsonlite`、`png`。基础工作台提供文献、PDF、写作和计算辅助工具，可以独立安装。

```powershell
git clone https://github.com/thekingofall/Biosoft-Project-Codex-Science.git
cd Biosoft-Project-Codex-Science
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.lock.txt
.\code\install-workbench.ps1
```

重新加载 Codex 的 MCP 与技能后，用 `$codex-science` 开始提问。

完整数据库连接器、原版技能资源读取和原版辅助函数执行需要另外提供本地 Claude Science 0.1.60 资源。配置方式见[安装说明](docs/setup.md)。模型权重和服务账户按相应提供方的要求准备。

## 这个版本覆盖到哪里

当前版本包含独立实现的科研工作台、现有数据库适配器、29 项本地技能的资源目录，以及 22 个经过测试的原版确定性辅助函数。论文阅读和写作由 Codex 与这些工具协同完成。

原版的持续笔记本、专用分子查看器、账户服务和完整任务调度仍有迁移工作。原版主程序已经开展静态分析，整套应用功能的等价性尚未建立。各模块的状态见[功能范围](docs/application-coverage.md)，详细目录见[能力清单](docs/capabilities.json)，测试方法见[验证说明](docs/validation.md)。

## 项目与来源

项目由独立的 Codex 适配代码组成，与 OpenAI、Anthropic 无官方隶属关系。仓库中的原创代码采用 [MIT License](LICENSE)。外部发行文件、模型权重和第三方资源保留各自许可，详见 [NOTICE](NOTICE.md)。
