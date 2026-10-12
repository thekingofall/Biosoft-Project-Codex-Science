# Validation / 验证范围

## Workbench 0.2.0

The local Windows environment passed 60 tests on 2026-10-12, including actual R plotting and multi-panel composition. These checks cover file handling and tool behavior; model predictions and scientific conclusions have separate validation requirements.

本轮 60 项测试通过，包含真实 PDF、Word 和 R 图件读写。实际 MCP 会话完成能力发现、原版辅助函数执行、稿件创建与 Word 导出、计算环境检查和 Crossref DOI 联网查询。Codex 主程序发现 23 个工作台工具，返回的工具加载错误为空。

| Check | Observed result |
|---|---|
| Local source catalog | All 29 skill directories represented |
| Reviewed kernel helpers | 22 original deterministic functions executed |
| PDF | Text, outline, page provenance, page rendering, search, identifiers and bounded continuation |
| Evidence | Matching page quotations accepted; absent or blank quotations rejected |
| Manuscripts | DOCX reopened; tables, images, emphasis and hyperlink relationships checked |
| Citation export | BibTeX/RIS/JSON formatting and DOI lookup failure behavior checked |
| Crossref online lookup | DOI 10.1038/nature12373 resolved to Nanometre-scale thermometry in a living cell (2013) |
| R figures | PDF and PNG generated; categorical identifiers such as 01 preserved |
| R composition | Two real rendering tests; panel proportions and PDF A/B labels checked |
| Compute | Shell argument quoting, resource fields, file hashes and 14 model recipes checked |
| Model HTTP transport | Actual local fixture requests; redirects blocked; nested escaped secrets redacted |
| Codex discovery | 23 workbench tools, no tool-loading error |

Run the checks:

```powershell
$env:CODEX_SCIENCE_TEST_TMP = 'D:\CodexTmp\science-tests'
$env:CODEX_SCIENCE_TEST_R = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe code\verify_workbench.py --online
.\.venv\Scripts\python.exe code\verify_codex_host.py science-workbench
```

The offline suite uses generated fixtures. Real source-helper tests skip when the separately supplied original assets are absent. R tests are enabled by the environment flag above; they require R, jsonlite and png. CI installs Python dependencies and runs offline tests without proprietary assets, internet service calls or model downloads.

当前未完成全部生物模型的数值推理测试，也未建立原版应用的整体行为等价性。原版持续笔记本、专用查看器、账户和完整云任务生命周期的状态见[功能范围](application-coverage.md)。

## Existing database adapter

The previous local acceptance against Claude Science 0.1.60 assets remains:

| Check | Observed result |
|---|---|
| MCP and Codex discovery | 224 unique enabled tools |
| Ensembl human BRCA1 | ENSG00000012048 |
| UniProt sequence | P04637 FASTA |
| PubChem aspirin | CID 2244 |
| Source exclusions | 23 excluded entries retained |

Other remote database operations have not each been exercised. Reports and catalogs remain in ignored local reports/ because they can contain machine details or third-party output. Run the verification commands to obtain fresh records.
