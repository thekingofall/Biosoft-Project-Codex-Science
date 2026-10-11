# Codex Science

[English](README.md) · **简体中文**

### 从一个科研问题，走到有来源、能复现的结果。

在 Codex 中输入 **`$codex-science`**，让它围绕你的问题完成证据检索、数据获取、分析、R 绘图和结果整理。

接入准备好的 Claude Science 0.1.60 本地发行文件后，`science-bio` 数据连接器提供 **23 个领域、224 个工具**。仓库包含自编适配层、技能、安装脚本和测试；连接器源码由使用者在本机单独提供。

## 可以用它做什么

| 你的需求 | 使用方式 |
| --- | --- |
| 查文献与背景证据 | 选择相应检索工具，保留来源和查询条件 |
| 查基因、蛋白、变异或药物 | 获取数据库记录及标准标识符 |
| 找公开组学数据 | 检索相应归档库，按研究目标筛选 |
| 分析自己的数据 | 核对实验设计，调用现有 R/Python 或授权的服务器环境 |
| 整理图件和报告 | 使用 R 绘图，保存 PNG/PDF、绘图数据及脚本 |

## 开始使用

需要 **Windows、Python 3.12、uv、Codex CLI**，以及单独准备的 Claude Science 0.1.60 本地资源与提取校验清单。先阅读[安装与外部资源要求](docs/setup.md)。技能提供工作流程指导，数据库连接需要这些外部资源；科学模型的运行环境需另行配置。

```powershell
git clone https://github.com/thekingofall/Biosoft-Project-Codex-Science.git
cd Biosoft-Project-Codex-Science
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.lock.txt
$env:CODEX_SCIENCE_RELEASE = 'D:\your-assets\0.1.60'
.\code\install-codex.ps1
.\.venv\Scripts\python.exe -X utf8 .\code\verify_mcp.py
```

重新加载 Codex 的技能与 MCP 连接后，直接说：

> $codex-science 帮我研究 BRCA1：核对基因信息，获取蛋白序列，整理带来源编号的结果。

> $codex-science 分析这个表达矩阵和样本表，先核对分组与批次，再做合适的差异分析，使用 R 输出图件和复现脚本。

## 查看状态与工具

```powershell
.\codex-science.ps1 status
.\codex-science.ps1 tools --query ensembl --limit 3
.\codex-science.ps1 tools --domain literature
```

状态命令区分当前配置和上一次在线测试。工具检索读取 `verify_mcp.py` 在本机生成的目录。

原始本机验收已通过 MCP 握手、Codex 发现 224 个工具，以及 BRCA1、TP53 蛋白和阿司匹林的实际查询。其余接口尚未逐项在线验证，详见[验证范围](docs/validation.md)。

## 需要补哪些配置

把 `user-settings.example.toml` 复制为 `user-settings.toml`，填写当前任务需要的字段。NCBI 接口需要联系邮箱，OpenAlex 需要 API Key，NCBI API Key 可选。邮箱会随相应查询提供给 NCBI，密钥按数据库认证方式使用。修改后重新连接 MCP；该配置文件保留在本机。

## 文件结构

```text
code/                 启动适配、安装和验证命令
skill/                科研工作流程与 Codex 显示信息
tests/                离线回归测试
docs/                 安装、验证及来源说明
reports/              本机生成的记录，排除在 Git 之外
```

## 来源与许可

Codex Science 是社区集成项目名称，本项目与 OpenAI、Anthropic 官方产品没有隶属关系。仓库内自编适配代码使用 MIT 许可；另行提供的 Claude Science 发行文件和依赖遵循各自条款。详见 [NOTICE](NOTICE.md)。
