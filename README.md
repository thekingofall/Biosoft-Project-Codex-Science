# Codex Science

**English** · [简体中文](README.zh-CN.md)

**Search papers, find data, analyze experiments, and make scientific figures in Codex.**

Codex Science is a toolkit for biomedical researchers who use Codex. It connects scientific databases to your conversation, so you can describe a research task in plain language, retrieve relevant records, and continue working with your own R, Python, or server environment.

If you are studying a gene, you can ask Codex for its identifiers, protein sequence, relevant papers, and public datasets. When you have your own expression matrix, you can continue by checking the sample groups, writing analysis code, making figures, and preparing a report.

**Built for people who already use Codex and want to bring it into everyday research.** The current installer supports Windows. Database access requires separately prepared local connector assets; see the [installation guide](docs/setup.md).

[Features](#what-can-you-do) · [Examples](#try-these-requests) · [Installation](#installation) · [FAQ](#frequently-asked-questions)

## What can you do?

### Find papers and understand a research question

Search services such as PubMed, arXiv, and OpenAlex, retrieve publication details, and ask Codex to organize the results around your question.

Use this for background reading, a gene-focused literature search, or finding papers about a method. Ask for titles, dates, identifiers, and source links so you can return to the original publications.

### Bring together gene and protein information

Look up standard gene identifiers, genomic coordinates, protein sequences, functional annotations, and pathway mappings through services including Ensembl, UniProt, GO, and Reactome.

For a candidate gene list, ask Codex to organize the identifiers, known functions, and related pathways into a useful reference for further investigation.

### Find public datasets for your study

Search resources such as GEO, ArrayExpress, and PRIDE for records relevant to a tissue, condition, or experiment type.

Use this to find reference cohorts, potential validation datasets, or earlier studies. Once you have candidates, ask Codex to inspect the available project information and study design before deciding what to download.

### Look up compounds, drugs, and clinical studies

Retrieve compound identifiers, drug-related records, and clinical trial information from sources such as PubChem, ChEMBL, and ClinicalTrials.gov.

For example, start with a compound name, establish its standard identifier, and then collect related target information or study records.

### Explore existing structures and interactions

Find existing structure records in PDB and AlphaFold DB, and retrieve protein interaction information from sources such as STRING.

This can provide structural context for a protein or help you examine known interactions among a group of candidates.

### Continue with your own analysis, figures, and reports

Provide your data and sample information, and the Codex Science workflow guides Codex to clarify the research question, groups, and data characteristics before writing and running code in your available environment.

Figure guidance defaults to R, with plot-ready data, scripts, and PNG/PDF exports kept together. These files let you revisit colors, labels, and layout later.

Analysis depends on Codex and your existing computing environment. Statistical methods must fit the study design, and the required R packages, Python packages, or scientific model runtimes must be configured for the task.

## Try these requests

After installation, type `$codex-science` in a Codex conversation and describe what you need.

**Get to know a gene**

> $codex-science I am studying human BRCA1. Find its Ensembl identifier, genomic coordinates, and UniProt protein sequence. Include the source links.

**Find papers for a research question**

> $codex-science Search for papers on T-cell aging and mitochondrial function. Group them by research question and include the main findings and original links.

**Find useful public data**

> $codex-science Find human peripheral-blood transcriptomic studies of aging in GEO. First organize their dataset identifiers, experiment types, and available sample information, then suggest which studies deserve a closer look.

**Analyze an expression matrix**

> $codex-science Here are an expression matrix and a sample sheet. Check the data type, groups, and batches, then choose a differential analysis suited to the study design. Make the figures in R and save the plot data and scripts.

These are example tasks. Literature and database queries depend on each service's access requirements; analysis needs actual data, sample information, and a working environment.

## How it works with Codex

| Part | What it does during your work |
| --- | --- |
| Codex | Understands the question, selects tools, writes and runs analysis code, and interprets results |
| The `$codex-science` skill | Guides the research workflow from retrieval through analysis, figures, and reporting |
| The `science-bio` connector | Queries scientific databases and returns their records to Codex |
| Your computing environment | Runs R, Python, and the scientific software needed for the task |

The currently supported connector provides **224 query operations across 23 domains**. Together with the workflow guidance, it lets you continue a research task within the same Codex conversation.

## Installation

You need **Windows, Codex CLI, Python 3.12, and uv**. Follow the [installation guide](docs/setup.md).

**You also need a prepared local Claude Science 0.1.60 connector directory and its manifest.** This GitHub repository supplies the adapter, skill, and installation scripts; the connector assets are supplied separately on your computer. The guide explains the required layout and configuration.

After installation, reload Codex skills and MCP connections to use `$codex-science`. MCP is the connection method Codex uses to call the database tools.

Some services require your own access settings:

| Service | What to configure |
| --- | --- |
| PubMed and other NCBI interfaces | Contact email; an NCBI API key is optional |
| OpenAlex | API key |

Store these settings in the local `user-settings.toml` file using the provided example. See the [installation guide](docs/setup.md) for details.

## Frequently asked questions

**Where do I use it?**

In a Codex conversation. Start your request with `$codex-science`, or ask Codex to use a specific tool from `science-bio`.

**Do I need to know how to code?**

You can describe the task in plain language and have Codex write the code. Research analysis still needs a clear study design, sample information, and criteria for interpreting the results.

**Can it work with my server?**

Codex can use a server you have configured and authorized it to access. Connections, data paths, software dependencies, and computing resources must be set up for your project.

**Can I query databases immediately after cloning?**

You must also prepare the local connector assets described in the installation guide and configure the services you need. Database integration cannot finish until those prerequisites are available.

**Will every feature work for my project?**

That depends on your data and environment. The adapter currently targets Claude Science 0.1.60; some interfaces require an email or key, and upstream services can change. See the [validation notes](docs/validation.md) for the checks actually performed.

## Further reading

[Installation and configuration](docs/setup.md) · [Validation scope](docs/validation.md) · [Workflow skill](skill/SKILL.md) · [Provenance](NOTICE.md)

Codex Science is an independent community integration. Authored code in this repository is [MIT licensed](LICENSE); external connectors, databases, and scientific software retain their own terms.
