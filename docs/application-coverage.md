# Application coverage and compute guide

[中文说明](#中文说明) · [Compute tools](#compute-tools) · [Evidence and remaining work](#evidence-and-remaining-work)

## 中文说明

Claude Science 0.1.60 的本地安装包包含科研数据库连接器、29 个科研技能目录，以及运行这些技能的桌面应用与任务系统。技能目录中的教程和 Python 辅助代码已经能够读取；模型权重、远端服务、原版应用账户和运行环境仍有各自的配置要求。

Codex Science 按实际科研任务接入这些能力。文献、写作和 PDF 工具的使用入口见项目 README。本页说明模型计算及应用基础设施的来源、已经提供的接口和剩余工作。

### 原版技能覆盖范围

| 用途 | 已识别的原版技能目录 | 计算或运行条件 |
|---|---|---|
| 文献与文章 | `literature-review`, `pdf-explore`, `paper-narrative`, `indication-dossier` | 文献来源、PDF 解析、模型阅读和写作能力 |
| 科研组图 | `figure-composer`, `figure-style` | 可用的绘图环境、图件和组图工具 |
| 结构预测与分子对接 | `alphafold2`, `boltz`, `chai1`, `diffdock`, `esmfold2`, `openfold3` | 对应模型环境、权重、GPU 或用户配置的模型服务 |
| 蛋白质序列设计 | `proteinmpnn`, `ligandmpnn`, `solublempnn` | 输入结构、模型代码与权重 |
| 序列与单细胞模型 | `borzoi`, `evo2`, `fair-esm2`, `scgpt`, `scvi-tools` | 对应软件、输入数据、必要的权重和计算资源 |
| 计算资源 | `compute-env-setup`, `remote-compute-ssh`, `remote-compute-modal`, `managed-model-endpoints`, `using-model-endpoint` | 用户自己的服务器、调度系统、云账户或模型服务 |
| 配置与技能管理 | `customize`, `skill-creator` | Codex 的技能和工具配置机制 |
| 产品与会话信息 | `product-self-knowledge`, `self-awareness` | 适配当前宿主产品的文档、历史和会话接口 |

这些目录代表安装包提供的技能说明范围。每个模型能否运行，还需要在目标环境中执行真实输入并检查输出。当前仓库的工具数量、技能目录数量均不能转换成整套应用的还原比例。

## Compute tools

The following five Python tools are independent Codex adapters. They use the observed public shape of the shipped workflows and standard local/HTTP interfaces. They do not depend on Claude Science's private `host.compute` daemon.

| Tool | What it does | Result |
|---|---|---|
| `science_model_recipe` | Returns observed input fields, entry points, weights and outputs for all 14 biological model skills | Source-hashed recipes; numerical execution remains environment-dependent |
| `science_compute_environment` | Inspects installed distributions, command locations, and NVIDIA device inventory | Environment report; GPU visibility does not establish model readiness |
| `science_prepare_compute_job` | Quotes an argument array, prepares Bash or Slurm directives, and hashes explicitly listed input files | Script text and a reproducibility manifest with state `prepared` |
| `science_model_endpoint_request` | Previews or sends JSON to an explicitly configured model API | Request digest, HTTP status and parsed JSON response |
| `science_capture_compute_result` | Hashes existing output files and records a supplied exit code | File provenance, with the process status explicitly marked as caller-reported |

### Choose a model recipe

Call `science_model_recipe` with an empty `model` to list all 14 models, or a name such as `boltz`, `scvi-tools` or `proteinmpnn` to read its structured recipe. Each recipe records the input format, observed CLI or Python entry point, required assets, output types, and the SHA-256 of the shipped source runbook. These records support deployment planning and script preparation. They do not install software or execute predictions. The inspected runbooks use CLI/Python interfaces; a model-specific HTTP endpoint must come from the chosen server documentation.

### Prepare a remote job

A Codex tool call can prepare a script:

```json
{
  "argv": ["python", "analysis.py", "--input", "counts.h5ad"],
  "input_files": ["/local/project/counts.h5ad", "/local/project/analysis.py"],
  "output_files": ["out/latent.csv"],
  "scheduler": "slurm",
  "job_name": "single-cell-integration",
  "cpus": 8,
  "memory_gib": 64,
  "time_minutes": 120,
  "gpus": 1,
  "partition": "gpu"
}
```

Use actual local paths and the target cluster's partition. Save the returned script and manifest, transfer the listed files, and submit through the user's configured SSH or scheduler tools after confirming the target allocation. Inputs remain at their original locations during preparation. Bash mode sets thread limits; Slurm mode also requests scheduler resources. Environment activation belongs in the selected executable or an existing reviewed wrapper script.

### Use a model endpoint

Create a private JSON configuration outside the repository, set `CODEX_SCIENCE_ENDPOINTS` to its absolute path in the MCP server environment, and restart that server. Choose the URL and routes from the model server's own API documentation.

```json
{
  "endpoints": {
    "my-model": {
      "base_url": "http://127.0.0.1:8000",
      "routes": ["/v1/infer"],
      "allow_requests": true
    }
  }
}
```

For a remote endpoint, use HTTPS and add `"api_key_env": "MY_MODEL_API_KEY"` if its API accepts a bearer token. Provide the secret through the server's process environment. The configuration contains the credential variable name. The `/v1/infer` route above is an example; use the exact route exposed by the configured service.

Call `science_model_endpoint_request` with `endpoint_name`, `route` and the model's native JSON `payload`. Its default `execute=false` returns a request preview. Set `execute=true` for an authorized actual call; the configuration must also enable `allow_requests`. Confirm any model-service charges before running paid inference. Requests and responses are limited to 4 MiB, the default timeout is 60 seconds, and HTTP redirects are refused. Binary downloads and asynchronous provider-specific polling need separate adapters.

The tool consumes an already-running service. Container lifecycle, weight downloads and GPU installation remain explicit setup steps. A successful HTTP response establishes a service response; prediction quality requires a scientific benchmark.

## Evidence and remaining work

### Source identity

The inspected distribution is Claude Science 0.1.60 Windows x64. Its installer SHA-256 is `b9339c9c49891dea244e8a62c03aadc65864c0993988eefb4e4d3a206057ff5e`. The extracted `main/claude-science.js` is 13,357,819 bytes with SHA-256 `d761d6294227ec546789554e1a4e5f5d46aa5dd17fd926b69803a46418e2a8e1`.

REA parsed this main JavaScript bundle as inert syntax: one JavaScript file, 2,947,689 visited AST nodes, 1,558 findings and zero parse failures. The semantic analysis exhausted the 2 GiB worker heap. Application and semantic coverage are partial; this record establishes syntax observations and preserves unknown relationships.

Retained REA parent evidence: `ev_43cd7e6ab51e428ed333c93ef9a874152ca2e8f8f5a0dd4a7a7b5587d4158d33`. Summary evidence: `ev_63fd35e57a9e4c2d94f936dcd0fe3aeb76027a6a11cf5668daa6e52d07ca76b9`. These identifiers refer to the analysis session. The supplied local distribution and the hashes above identify the input for a fresh analysis.

### Application features beyond the 29 skills

| Application surface | Local evidence | Codex adaptation and remaining work |
|---|---|---|
| Database queries | `mcp-servers/bio-tools` contains domain modules and tool gates | Existing adapter retains the source's enabled tool set; endpoint-specific service tests remain necessary |
| Python and R execution | Main bundle declares `python`, `r`, `repl`, `manage_environments`, `manage_packages` | Codex uses its own authorized execution tools and installed environments; original persistent kernel orchestration has not been reproduced |
| Artifact storage and previews | Main bundle contains `save_artifacts`, artifact version structures and types for PDF, CSV, DOCX, LaTeX, notebooks, structures, molecules, genomes and MSA | File provenance is available; original version database, interactive viewers and full artifact lifecycle need dedicated reconstruction |
| Article full-text retrieval | Main bundle has a `fetch_article_fulltext` description and handling code | Literature adapters can access permitted open sources; institutional proxy and publisher credentials require explicit configuration |
| SSH and scheduler jobs | `skills/remote-compute-ssh/SKILL.md` describes staging, submit, status, harvesting and notifications | Job scripts and provenance are implemented; automatic remote staging, daemon polling, cancellation and harvesting remain pending |
| Modal cloud jobs | `skills/remote-compute-modal` and `compute/operon_compute_provider` expose provider contracts | Provider setup and accounts remain required; cloud dispatch has not been validated in this adaptation |
| Model services | `skills/using-model-endpoint/provider.py` and managed endpoint runbook define native HTTP calls and daemon-owned lifecycle | Configured native HTTP calls are implemented; automatic container start/stop and weight/cache management remain pending |
| Agent profiles and skills | Main bundle and `skills/customize` refer to `host.agents.*` and `host.skills.*` | Codex skill registration is available; the original profile editor and daemon SDK are separate application work |
| Session history and accounting | `skills/self-awareness` and SQL migrations describe `host.query` and session tables | Codex owns its session store; original schema compatibility and token/cost accounting are not reconstructed |
| Authentication and hosted inference | Main bundle contains OAuth, account, usage, model routing and service-client code | Users continue through their authorized Codex or model-provider accounts; hosted model implementation and service-side state are outside the local installer |

Main-bundle token inspection corroborates surface names and nearby handling code. It does not establish that each branch is reachable in a running original application. Original desktop runtime parity, numerical GPU model parity and a complete UI/API inventory remain open work. No overall completion percentage is justified by this evidence.

### Local tests

`tests/test_compute_tools.py` exercises seven cases: script quoting and input hashes, invalid resource/directive rejection, observed-file versus reported-exit provenance, a real loopback HTTP request with authentication and redaction, redirect refusal and endpoint authorization, MCP registration, and all 14 source-anchored model recipes. The loopback response is a deterministic fixture; actual scientific model predictions require configured services and model-specific benchmark inputs.
