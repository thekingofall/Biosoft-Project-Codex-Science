# 在服务器上连续分析 / Research on your server

[简体中文](#简体中文) · [English](#english)

## 简体中文

把数据留在服务器，在 Codex 里继续分析。你可以先用 Python 读入数据，再分几轮查看和计算；R 会话也能保留对象，继续整理统计结果和绘图。每次执行会写进 `.ipynb` 笔记本，代码、输出和报错保存在一起。

较长的分析可提交为后台任务。关闭 SSH 连接后任务继续运行，稍后可以查询进度、读日志、取消任务，或下载选定结果。下载时比较 SHA-256 校验值；单个文件上限为 100 MiB，较大的数据继续留在服务器。

### 直接这样问 Codex

```text
$codex-science
检查服务器连接，在项目目录创建一个 Python 会话。
读取我指定的 CSV，检查样本数和缺失值，保留会话供下一步使用。
```

```text
$codex-science
用 R 继续分析这份结果，保存统计表和绘图脚本。
把长时间运行的部分提交到后台，告诉我任务编号和日志位置。
```

```text
$codex-science
查询刚才的任务。完成后把选定的结果表和笔记本下载到当前项目，核对文件校验值。
```

### 安装到一个独立目录

准备 Linux 服务器、已有的 Mamba 和有写权限的项目目录。下面的路径是示例。所有依赖进入该目录下的 Conda 环境；模型权重按研究任务另外配置。

```bash
PROJECT=/path/to/Codex-Science
mkdir -p "$PROJECT/code" "$PROJECT/runtime/conda-pkgs"
# 把仓库的 environment.remote.yml、code/remote_runtime.py、code/start_remote.py
# 分别上传到项目根目录和 code 目录。
CONDA_PKGS_DIRS="$PROJECT/runtime/conda-pkgs" mamba env create \
  --prefix "$PROJECT/envs/runtime" --file "$PROJECT/environment.remote.yml"
"$PROJECT/envs/runtime/bin/python" "$PROJECT/code/start_remote.py" --root "$PROJECT"
```

Python、R、IRkernel、Jupyter、NumPy、pandas、SciPy 和 ggplot2 都在独立环境中。启动脚本在这个环境注册内核，服务使用账户私有 Unix socket，经 SSH 访问。环境定义适用于 CPU 数据分析。

本地安装 `requirements.lock.txt` 后，把以下配置写入 `.local/remote.json`，或者用 `CODEX_SCIENCE_REMOTE_CONFIG` 指定私有文件。服务器地址、账户与私钥请填自己的配置。`host_key_sha256` 是可信公钥原始字节的 SHA-256 十六进制值，必须先独立核实服务器身份。

```json
{
  "host": "your-server.example.org",
  "port": 22,
  "user": "researcher",
  "root": "/path/to/Codex-Science",
  "known_hosts": "~/.ssh/known_hosts",
  "host_key_alias": "your-server.example.org",
  "host_key_sha256": "verified-public-key-sha256-hex",
  "identity_file": "~/.ssh/research_key"
}
```

密码登录可用 `password_env` 指定环境变量名称。已有私人账号表也可通过 `credentials_markdown` 和 `credential_server` 接入；账号表保持在原位置。私有配置与凭据均保留在 Git 忽略目录外部或 `.local` 中。

### 文件在哪里

| 目录 | 内容 |
|---|---|
| `envs/runtime` | 独立的 Conda 环境 |
| `projects/<项目名>` | 分析数据、脚本和结果 |
| `sessions/<会话编号>` | 笔记本、内核日志与会话记录 |
| `jobs/<任务编号>` | 提交代码、状态、输出与错误日志 |
| `runtime`、`logs` | 服务状态、临时文件与运行日志 |

单个会话执行最长 90 秒，长期分析使用后台任务。最多同时保留 8 个交互会话；任务最长 7 天。`cpus` 控制常见数学库的线程数量，任务消耗的总内存和 CPU 仍需按服务器资源安排。当前服务面向一个可信账户，按顺序处理交互请求。

SSH 断开后会话和任务仍可继续。服务器重启会清空内存中的对象并终止进程；笔记本和已写入磁盘的结果保留。重启后运行上面的启动命令，再根据保存的代码恢复分析。服务启动由项目脚本管理。

当前提供 Python/R 持续执行、笔记本记录与导出、后台作业管理。可视化笔记本网页、多用户权限、Slurm 队列管理、Modal 账户、原版云端服务和专用分子查看器仍需分别集成。

## English

Keep data on your Linux server and work from Codex. Persistent Python and R sessions retain variables between calls and save executed code, outputs and errors in Jupyter notebooks. Detached jobs support status queries, logs, cancellation and timeouts. Selected artifacts can be downloaded with SHA-256 verification, up to 100 MiB each.

Create the project-local Mamba environment using `environment.remote.yml`, upload the two runtime scripts, and run `code/start_remote.py` with that environment's Python. The commands and private SSH profile above show the setup. Verify the server's host key before filling the fingerprint. The runtime uses an owner-only Unix socket carried through authenticated SSH. Submitted code executes with that account's permissions.

Call `science_remote` with an action and a `parameters` object:

| Action | Parameters |
|---|---|
| `health`, `sessions`, `jobs` | `{}` |
| `session_start` | `language: python/r`, `project: projects/my-study`, `name` |
| `session_execute` | `session_id`, `code`, `timeout: 1..90` |
| `session_close` | `session_id` |
| `job_submit` | `language: python/r/bash`, `code`, `project`, `timeout`, `cpus` |
| `job_status`, `job_cancel` | `job_id` |
| `job_logs` | `job_id`, `stream: stdout/stderr/worker`, `offset`, `limit` |
| `file_write` | `path: projects/...`, `text`, `overwrite: false` |
| `artifacts`, `artifact_info` | `path` |

`science_fetch_artifact(remote_path, workspace, output)` downloads to a relative local path and preserves existing files. Sessions support up to 8 live kernels; jobs have a maximum duration of 7 days. Thread settings guide numerical libraries and do not impose OS resource quotas. This is a single-account service with serial interactive requests. SSH disconnects preserve work; a server reboot requires restarting the runtime and re-running code to recreate memory state.

The current scope covers persistent execution, notebook records and detached job management. A notebook web editor, multi-user access, Slurm dispatch, Modal provisioning, hosted account services and specialized molecular viewers need additional integration.

Implementation reference: [Jupyter client API](https://jupyter-client.readthedocs.io/en/stable/api/jupyter_client.blocking.html).
