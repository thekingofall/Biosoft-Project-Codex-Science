# Codex Science

**English** · [简体中文](README.zh-CN.md)

**Bring papers, data, analysis and manuscript writing into one Codex workflow.**

Codex Science is a research toolkit for biomedical work. Describe a question and let Codex retrieve scientific records, read local papers, organize evidence, write analysis code, make figures and revise a manuscript. Outputs stay in your project as editable files.

For example, start with a question about T-cell ageing: find primary studies, compare their populations and methods, keep a page-linked evidence table, and use that evidence to develop an introduction or discussion around your own results.

[Literature and writing](#from-papers-to-manuscripts) · [Databases and models](#scientific-databases-and-models) · [Examples](#try-these-requests) · [Install](#install) · [Coverage](docs/application-coverage.md)

## From papers to manuscripts

### Find papers and keep usable references

Search Crossref and resolve DOI metadata. The database connector adds PubMed, arXiv, OpenAlex, bioRxiv and other sources. Codex can compare findings, identify disagreements and organize a source-backed review. Export references as **BibTeX, RIS or JSON**.

Crossref is available through the standalone workbench. Other providers may require a contact email or API key. Scientific claims still need to be checked against the primary paper.

### Read PDFs with page-level provenance

Read bookmarks and selected pages, search passages, extract DOI and GEO candidates, and render pages for figure inspection. Evidence tables retain claims, sources, pages, quotations, findings and limitations. Local PDF quotations are checked against their cited page.

Page search uses literal text matching. Codex can read rendered pages or use an available OCR tool for scanned documents. Long documents can be covered in bounded batches.

### Develop a paper's argument and an editable draft

Ask Codex to read your abstract, results and figure captions, then assess the research question, figure order, supporting evidence and missing analyses. Continue with introductions, results, discussions, captions or a structured indication dossier.

Keep manuscripts in Markdown and export to **Word**. The exporter supports headings, paragraphs, lists, tables, emphasis, links and local images; complex equations retain their source text. A manuscript check flags empty sections, unresolved citation markers and missing figures.

## From data to figures

Use your existing R, Python or server environment for analysis. The built-in R plotting tool turns prepared CSV tables into scatter, line, box or bar plots, saving **PDF, PNG, input checksums and reproduction parameters**. It uses English labels, Arial and a shared palette.

Compose existing PNG panels in a regular or 12-column grid, preserve their aspect ratios, add Arial panel letters, and export PDF/PNG with provenance.

For more specialized single-cell, enrichment or spatial analysis, Codex works with the relevant software and analysis skills. Keep scripts, plot-ready tables and figures in the project for later revision.

## Scientific databases and models

The database connector exposes 224 query operations across 23 domains, including gene, protein, pathway, compound, trial and public omics records. Sources include Ensembl, UniProt, PubChem, GEO and ChEMBL. Provider configuration and availability vary.

The model catalog provides input formats, actual software entry points, weight requirements and expected outputs:

| Research task | Models and software |
|---|---|
| Structure prediction and docking | AlphaFold2, Boltz, Chai-1, DiffDock, ESMFold2, OpenFold3 |
| Protein sequence design | ProteinMPNN, LigandMPNN, SolubleMPNN |
| Sequence and regulatory models | ESM2, Evo2, Borzoi |
| Single-cell models | scGPT, scvi-tools |

Each model needs its own environment, weights and compute. Codex Science can inspect local resources, prepare Bash/Slurm jobs, call a configured model endpoint and record output hashes. Full inference across all models remains unvalidated.

## Try these requests

```text
$codex-science
Find primary studies on T-cell ageing. Compare populations, methods and
findings, keep traceable citations, and export a RIS bibliography.
```

```text
$codex-science
Read the three PDFs in this project. Compare their batch-correction methods,
record limitations and page references, and write a connected synthesis.
```

```text
$codex-science
Read manuscript.md and the figures folder. Improve the scientific argument,
revise the results and discussion, check missing references, and export Word.
```

```text
$codex-science
Check whether my compute environment can run Boltz. Identify required inputs
and weights, and prepare a script before any model deployment.
```

## Install

Requires **Python 3.12, Codex and MCP support**. R plots additionally need R and `jsonlite`/`png`. The literature, PDF, manuscript and compute workbench can be installed independently.

```powershell
git clone https://github.com/thekingofall/Biosoft-Project-Codex-Science.git
cd Biosoft-Project-Codex-Science
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.lock.txt
.\code\install-workbench.ps1
```

Reload Codex MCP connections and skills, then start with `$codex-science`.

The full database connector, original skill reference reader and original helper execution additionally require locally supplied Claude Science 0.1.60 assets. See [setup](docs/setup.md). Obtain model weights and service accounts under their respective terms.

## Current coverage

This release combines an independently implemented research workbench, the existing database adapter, a catalog of 29 local skill resources, and 22 tested deterministic helpers from locally supplied kernels. Codex performs document reading, synthesis and drafting with these tools.

Persistent notebooks, specialized molecular viewers, account services and the complete original job lifecycle still require integration. Static analysis of the original application is underway; application-wide behavioral equivalence has not been established. See [coverage](docs/application-coverage.md), the [capability catalog](docs/capabilities.json), and [validation](docs/validation.md).

## Project and sources

An independent Codex adapter, with no official affiliation with OpenAI or Anthropic. Original adapter code uses the [MIT License](LICENSE). External distributions, model weights and third-party resources retain their own licenses. See [NOTICE](NOTICE.md).
