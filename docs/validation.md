# Validation / 验证范围

The original local Windows installation was tested on 2026-10-12 against prepared Claude Science 0.1.60 assets.

| Check | Observed result |
| --- | --- |
| MCP initialization and tool listing | 224 unique tools |
| Codex app-server discovery | 224 tools; no tool-loading error |
| Ensembl human BRCA1 lookup | ENSG00000012048 |
| UniProt sequence retrieval | P04637 FASTA |
| PubChem aspirin lookup | CID 2244 |
| Invalid argument type | Rejected |
| Source exclusions | 23 excluded entries retained |

原始本机已验证以上范围。工具能被列出，不代表其远程接口已逐项通过运行测试。完整分析工作流程还取决于用户的数据、设计与计算环境。

Live reports and the generated tool catalog stay local because they can include workstation details or third-party output. Run the verification commands to produce your own records.

CI runs offline adapter tests on synthetic fixtures. It does not download proprietary assets, start Claude Science, call scientific services or establish end-to-end scientific validity.
