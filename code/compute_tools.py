"""Portable compute preparation, endpoint calls, and file provenance for Codex."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_RESPONSE = 4 * 1024 * 1024


def _file_record(path: str) -> dict:
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file():
        raise ValueError("Expected a regular file")
    before = p.stat()
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    after = p.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("File changed while hashing; retry when writing has stopped")
    return {"path": str(p), "bytes": after.st_size, "sha256": digest.hexdigest()}


def science_compute_environment() -> dict:
    """Inspect local interpreters, installed scientific distributions, and NVIDIA devices."""
    packages = {}
    for name in ("numpy", "scipy", "pandas", "torch", "jax", "scanpy", "scvi-tools", "modal", "requests"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    commands = {name: shutil.which(name) for name in ("Rscript", "ssh", "scp", "sbatch", "docker", "nvidia-smi")}
    gpu = {"status": "unavailable", "devices": []}
    if commands["nvidia-smi"]:
        try:
            result = subprocess.run([commands["nvidia-smi"], "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=10, check=False)
            gpu = {"status": "detected" if result.returncode == 0 else "probe_failed", "devices": result.stdout.strip().splitlines() if result.returncode == 0 else []}
        except (OSError, subprocess.TimeoutExpired):
            gpu["status"] = "probe_failed"
    return {"python": sys.version.split()[0], "executable": sys.executable, "platform": platform.platform(), "packages": packages, "commands": commands, "gpu": gpu, "scope": "Local environment inventory; model weights and numerical inference have not been tested."}


def science_prepare_compute_job(argv: list[str], input_files: list[str], output_files: list[str], scheduler: str = "bash", job_name: str = "science-job", cpus: int = 4, memory_gib: int = 16, time_minutes: int = 60, gpus: int = 0, partition: str = "", account: str = "") -> dict:
    """Prepare a portable Bash/Slurm script and input checksums. Returns text; submits no job."""
    if scheduler not in {"bash", "slurm"}:
        raise ValueError("scheduler must be bash or slurm")
    if not argv or any(not isinstance(x, str) or "\x00" in x for x in argv) or not argv[0].strip():
        raise ValueError("argv must contain a nonempty executable and string arguments")
    for key, value in (("job_name", job_name), ("partition", partition), ("account", account)):
        if (key == "job_name" and not value) or (value and not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value)):
            raise ValueError(f"Invalid {key}")
    for key, value, upper in (("cpus", cpus, 4096), ("memory_gib", memory_gib, 1048576), ("time_minutes", time_minutes, 525600)):
        if type(value) is not int or not 1 <= value <= upper:
            raise ValueError(f"Invalid {key}")
    if type(gpus) is not int or not 0 <= gpus <= 1024:
        raise ValueError("Invalid gpus")
    if len(input_files) > 1000 or len(output_files) > 1000:
        raise ValueError("At most 1000 input and output paths are accepted")
    for output in output_files:
        path = Path(output)
        if not output or path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", output) or "\x00" in output:
            raise ValueError("Expected output paths must be relative to the remote job directory")
    inputs = [_file_record(path) for path in input_files]
    lines = ["#!/usr/bin/env bash"]
    if scheduler == "slurm":
        lines.extend([f"#SBATCH --job-name={job_name}", f"#SBATCH --cpus-per-task={cpus}", f"#SBATCH --mem={memory_gib}G", f"#SBATCH --time={time_minutes}", "#SBATCH --output=job-%j.out", "#SBATCH --error=job-%j.err"])
        if gpus:
            lines.append(f"#SBATCH --gres=gpu:{gpus}")
        if partition:
            lines.append(f"#SBATCH --partition={partition}")
        if account:
            lines.append(f"#SBATCH --account={account}")
    lines.extend(["set -euo pipefail", f"export OMP_NUM_THREADS={cpus}", f"export MKL_NUM_THREADS={cpus}", f"export OPENBLAS_NUM_THREADS={cpus}", "exec " + shlex.join(argv)])
    script = "\n".join(lines) + "\n"
    spec = {"schema_version": 1, "job_name": job_name, "scheduler": scheduler, "argv": argv, "inputs": inputs, "expected_outputs": output_files, "resources": {"cpus": cpus, "memory_gib": memory_gib, "time_minutes": time_minutes, "gpus": gpus, "partition": partition, "account": account}, "script_sha256": hashlib.sha256(script.encode()).hexdigest()}
    return {"state": "prepared", "script": script, "manifest": spec, "next_action": "Save job.sh and this manifest, stage inputs explicitly, confirm the target environment and allocation, then dispatch with the authorized SSH or scheduler tool.", "resource_enforcement": "Slurm directives request these resources; bash mode sets thread counts only."}


def science_capture_compute_result(output_files: list[str], reported_exit_code: int | None = None, job_id: str = "") -> dict:
    """Hash existing result files and record an explicitly reported process exit status."""
    if len(output_files) > 1000:
        raise ValueError("At most 1000 output paths are accepted")
    if reported_exit_code is not None and type(reported_exit_code) is not int:
        raise ValueError("reported_exit_code must be an integer or null")
    return {"schema_version": 1, "captured_at": datetime.now(timezone.utc).isoformat(), "job_id": job_id, "files": [_file_record(p) for p in output_files], "reported_exit_code": reported_exit_code, "process_status_source": "caller_report" if reported_exit_code is not None else "unknown", "scientific_validation": "not_assessed"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _endpoint(name: str, route: str) -> tuple[dict, str]:
    setting = os.environ.get("CODEX_SCIENCE_ENDPOINTS")
    if not setting:
        raise ValueError("Set CODEX_SCIENCE_ENDPOINTS to a local endpoint configuration JSON file")
    config = json.loads(Path(setting).expanduser().read_text(encoding="utf-8-sig"))
    endpoint = config.get("endpoints", {}).get(name)
    if not isinstance(endpoint, dict):
        raise ValueError("Unknown configured endpoint")
    base = endpoint.get("base_url", "")
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Endpoint base URL must have a host and no credentials, query, or fragment")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Remote endpoints must use HTTPS")
    if route not in endpoint.get("routes", []) or not route.startswith("/") or route.startswith("//") or any(c in route for c in ("?", "#", "\\", "\r", "\n")) or ".." in urllib.parse.unquote(route).split("/"):
        raise ValueError("Route must exactly match a configured absolute API route")
    key_env = endpoint.get("api_key_env", "")
    if key_env and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", key_env):
        raise ValueError("api_key_env must name an environment variable")
    return endpoint, base.rstrip("/") + route


def science_model_endpoint_request(endpoint_name: str, route: str, payload: dict, execute: bool = False, timeout_seconds: int = 60) -> dict:
    """Preview or call a user-configured model API. execute=True requires allow_requests in its configuration. No model daemon or container is started."""
    endpoint, url = _endpoint(endpoint_name, route)
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 300:
        raise ValueError("timeout_seconds must be between 1 and 300")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(body) > MAX_RESPONSE:
        raise ValueError("Request exceeds the 4 MiB limit")
    summary = {"endpoint": endpoint_name, "route": route, "request_bytes": len(body), "request_sha256": hashlib.sha256(body).hexdigest()}
    if not execute:
        return {**summary, "state": "preview", "requests_allowed": endpoint.get("allow_requests") is True}
    if endpoint.get("allow_requests") is not True:
        raise ValueError("This endpoint has not been enabled for requests")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = ""
    if endpoint.get("api_key_env"):
        key = os.environ.get(endpoint["api_key_env"], "")
        if not key:
            raise ValueError("Configured endpoint credential is missing")
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout_seconds) as response:
            content = response.read(MAX_RESPONSE + 1)
            if len(content) > MAX_RESPONSE:
                raise ValueError("Endpoint response exceeds the 4 MiB limit")
            text = content.decode("utf-8")
            result = json.loads(text)
            def scrub(value):
                if isinstance(value,str): return value.replace(key,"[redacted]")
                if isinstance(value,list): return [scrub(v) for v in value]
                if isinstance(value,dict): return {scrub(k):scrub(v) for k,v in value.items()}
                return value
            if key: result = scrub(result)
            return {**summary, "state": "responded", "http_status": response.status, "response": result}
    except urllib.error.HTTPError as exc:
        return {**summary, "state": "http_error", "http_status": exc.code, "redirects_followed": False}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {**summary, "state": "connection_error"}


_MODEL_RECIPES = {'alphafold2': {'assets': ['AlphaFold2 model parameters',
                           'MSA from the configured MMseqs2 service or a staged alignment'],
                'inputs': {'input.fasta': 'Protein FASTA; multimers follow ColabFold chain syntax'},
                'invocation': {'argv': ['colabfold_batch',
                                        'input.fasta',
                                        'out',
                                        '--num-recycle',
                                        '3',
                                        '--model-type',
                                        'alphafold2_multimer_v3']},
                'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use '
                                       'the configured server documentation.',
                'outputs': ['Ranked predicted structures', 'pLDDT and complex confidence scores'],
                'purpose': 'Protein monomer and multimer structure prediction',
                'runtime_tested': False,
                'software': ['ColabFold', 'AlphaFold2'],
                'source': {'path': 'skills/alphafold2/SKILL.md',
                           'release': '0.1.60',
                           'sha256': '562520a36043c09f6e740b28a097e1e11a68b73bcc3c4c7cb0e269a644b4427a'},
                'status': 'recipe_prepared'},
 'boltz': {'assets': ['Boltz model weights', 'MSA when requested'],
           'input_example': {'sequences': [{'protein': {'id': 'A', 'sequence': 'MQIFVK'}},
                                           {'ligand': {'id': 'L', 'smiles': 'CCO'}}],
                             'version': 1},
           'inputs': {'complex.yaml': 'YAML version=1; sequences entries contain protein.id/sequence or '
                                      'ligand.id/smiles/ccd'},
           'invocation': {'argv': ['boltz',
                                   'predict',
                                   'complex.yaml',
                                   '--use_msa_server',
                                   '--out_dir',
                                   'out',
                                   '--recycling_steps',
                                   '3',
                                   '--diffusion_samples',
                                   '5']},
           'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use the '
                                  'configured server documentation.',
           'outputs': ['Complex structures', 'Confidence outputs'],
           'purpose': 'Protein, nucleic-acid and ligand complex prediction',
           'runtime_tested': False,
           'software': ['boltz'],
           'source': {'path': 'skills/boltz/SKILL.md',
                      'release': '0.1.60',
                      'sha256': '4205a08363955f762f45a2065263de0dabedd898eba13460830b70b621b26700'},
           'status': 'recipe_prepared'},
 'borzoi': {'assets': ['johahi/borzoi-replicate-0', 'HF_HOME cache'],
            'inputs': {'dna': 'One-hot tensor (batch, 4, 524288)'},
            'invocation': {'positional_arguments': ['johahi/borzoi-replicate-0'],
                           'operation': 'Load model, move to selected device, and apply to the prepared '
                                        'tensor',
                           'python_entry': 'borzoi_pytorch.Borzoi.from_pretrained'},
            'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use the '
                                   'configured server documentation.',
            'notes': ['Genomic coordinates and track identities must be retained alongside predictions'],
            'outputs': ['Tensor (batch, tracks, 6144)'],
            'purpose': 'DNA sequence to functional genomic tracks',
            'runtime_tested': False,
            'software': ['borzoi_pytorch', 'torch'],
            'source': {'path': 'skills/borzoi/SKILL.md',
                       'release': '0.1.60',
                       'sha256': 'a6b87d906c21eb51c141f7510b2e77ef8eab7127abb17a66467043408d92d702'},
            'status': 'recipe_prepared'},
 'chai1': {'assets': ['Chai-1 weights'],
           'inputs': {'complex.fasta': 'Typed headers such as >protein|name=target and '
                                       '>ligand|name=cofactor; sequence or SMILES on following line'},
           'invocation': {'arguments': {'device': 'cuda:0',
                                        'fasta_file': 'Path(complex.fasta)',
                                        'num_diffn_timesteps': 200,
                                        'num_trunk_recycles': 3,
                                        'output_dir': 'Path(out)',
                                        'seed': 42,
                                        'use_esm_embeddings': True},
                          'python_entry': 'chai_lab.chai1.run_inference'},
           'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use the '
                                  'configured server documentation.',
           'outputs': ['Candidate structures', 'ranking_data aggregate_score'],
           'purpose': 'Protein and ligand co-folding',
           'runtime_tested': False,
           'software': ['chai_lab'],
           'source': {'path': 'skills/chai1/SKILL.md',
                      'release': '0.1.60',
                      'sha256': '14c7b111475cfb2df0c1ba4de8427b09099439417101bc443fe52e8c80eff539'},
           'status': 'recipe_prepared'},
 'diffdock': {'assets': ['DiffDock model checkpoints',
                         'Configured repository and inference dependencies'],
              'inputs': {'default_inference_args.yaml': 'Repository inference configuration',
                         'ligand_description': 'SMILES or ligand input accepted by DiffDock',
                         'target.pdb': 'Protein coordinates'},
              'invocation': {'argv': ['python',
                                      '-m',
                                      'inference',
                                      '--config',
                                      'default_inference_args.yaml',
                                      '--protein_path',
                                      'target.pdb',
                                      '--ligand_description',
                                      'COc1ccc(C#N)cc1',
                                      '--out_dir',
                                      'out'],
                             'working_directory': 'DiffDock repository'},
              'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use the '
                                     'configured server documentation.',
              'notes': ['Pose ranking is not a measured binding affinity'],
              'outputs': ['Ranked ligand poses', 'Model confidence'],
              'purpose': 'Small-molecule binding pose prediction',
              'runtime_tested': False,
              'software': ['DiffDock repository', 'torch'],
              'source': {'path': 'skills/diffdock/SKILL.md',
                         'release': '0.1.60',
                         'sha256': '6c3acc1710209b8daf2322e6103043c3487412153e2455deab6abd851ad8efb6'},
              'status': 'recipe_prepared'},
 'esmfold2': {'assets': ['biohub/ESMFold2 or biohub/ESMFold2-Fast',
                         'HF_HOME cache',
                         'Compatible PyTorch and optional attention kernels'],
              'inputs': {'sequences': 'StructurePredictionInput with ProteinInput, DNAInput, RNAInput '
                                      'or LigandInput; optional per-chain MSA'},
              'invocation': {'arguments': {'num_diffusion_samples': 5,
                                           'num_loops': 10,
                                           'num_sampling_steps': 68,
                                           'seed': 0},
                             'model_id': 'biohub/ESMFold2',
                             'model_loader': 'transformers.models.esmfold2.modeling_esmfold2.ESMFold2Model.from_pretrained',
                             'python_entry': 'esm.models.esmfold2.ESMFold2InputBuilder.fold'},
              'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use the '
                                     'configured server documentation.',
              'notes': ['This recipe records the shipped version; upstream installation compatibility '
                        'needs verification on the target host'],
              'outputs': ['Prediction.complex.to_mmcif()', 'plddt', 'ptm', 'iptm', 'pae'],
              'purpose': 'Biohub ESMFold2 all-atom co-folding',
              'runtime_tested': False,
              'software': ['esm at Biohub/esm f652b471',
                           'Biohub/transformers 3a8956fb4d4ea16b0ec8e71deef2c2909b6a5cbf'],
              'source': {'path': 'skills/esmfold2/SKILL.md',
                         'release': '0.1.60',
                         'sha256': '28e625bab51a5d33e278b5ee6f304d76afa35c424fd919e1914d649df7600175'},
              'status': 'recipe_prepared'},
 'evo2': {'assets': ['evo2_7b or evo2_40b weights', 'Compatible GPU kernels', 'HF_HOME cache'],
          'inputs': {'prompt_seqs': 'DNA prefixes for generation',
                     'sequences': 'List of DNA strings for score_sequences'},
          'invocation': {'model_id': 'evo2_7b',
                         'operations': {'generate': {'n_tokens': 256,
                                                     'prompt_seqs': ['ATGAAAGCT'],
                                                     'temperature': 0.7},
                                        'score_sequences': {'positional_arguments': [['ATCGATCG']]}},
                         'python_entry': 'evo2.Evo2'},
          'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use the '
                                 'configured server documentation.',
          'outputs': ['Per-sequence log-likelihood scores', 'Generated DNA sequences'],
          'purpose': 'DNA likelihood scoring, embeddings and generation',
          'runtime_tested': False,
          'software': ['evo2', 'torch'],
          'source': {'path': 'skills/evo2/SKILL.md',
                     'release': '0.1.60',
                     'sha256': '60144f18b7b6d5ebe903dea982ddd30f0bb19f6c8a8aec62f1539c2b972768b3'},
          'status': 'recipe_prepared'},
 'fair-esm2': {'assets': ['ESM-2 650M checkpoint', 'TORCH_HOME cache'],
               'inputs': {'sequences': 'List of (name, amino-acid sequence) pairs processed with '
                                       'alphabet.get_batch_converter()'},
               'invocation': {'forward_arguments': {'repr_layers': [33]},
                              'pooling': 'Exclude BOS and EOS before mean pooling residue '
                                         'representations',
                              'python_entry': 'esm.pretrained.esm2_t33_650M_UR50D'},
               'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use the '
                                      'configured server documentation.',
               'outputs': ['Layer 33 residue embeddings', 'Mean sequence embedding'],
               'purpose': 'Protein representations and sequence scoring',
               'runtime_tested': False,
               'software': ['fair-esm', 'torch'],
               'source': {'path': 'skills/fair-esm2/SKILL.md',
                          'release': '0.1.60',
                          'sha256': 'da5729e9014848de10296149541ccac30696144ba14c28f003de4cfdd9771480'},
               'status': 'recipe_prepared'},
 'ligandmpnn': {'assets': ['model_params/ligandmpnn_v_32_010_25.pt'],
                'inputs': {'complex.pdb': 'Structure containing backbone and desired atomic context',
                           'fixed_residues': 'Space-separated chain/residue identifiers, for example '
                                             'A45 A46'},
                'invocation': {'argv': ['python',
                                        'run.py',
                                        '--model_type',
                                        'ligand_mpnn',
                                        '--checkpoint_ligand_mpnn',
                                        './model_params/ligandmpnn_v_32_010_25.pt',
                                        '--pdb_path',
                                        'complex.pdb',
                                        '--out_folder',
                                        'out',
                                        '--batch_size',
                                        '8',
                                        '--number_of_batches',
                                        '4',
                                        '--temperature',
                                        '0.1',
                                        '--fixed_residues',
                                        'A45 A46'],
                               'working_directory': 'LigandMPNN repository'},
                'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use '
                                       'the configured server documentation.',
                'outputs': ['Designed FASTA sequences', 'Threaded PDB structures'],
                'purpose': 'Sequence design with ligand, nucleic-acid and metal context',
                'runtime_tested': False,
                'software': ['dauparas/LigandMPNN at 26ec57ac976ade5379920dbd43c7f97a91cf82de'],
                'source': {'path': 'skills/ligandmpnn/SKILL.md',
                           'release': '0.1.60',
                           'sha256': '406c8497ebccc95a50839037a359a6b96a24fe9120126e4efc83bff741610c49'},
                'status': 'recipe_prepared'},
 'openfold3': {'assets': ['OpenFold/OpenFold3 checkpoints/of3-p2-155k.pt', 'OPENFOLD_CACHE'],
               'input_example': {'queries': {'my_complex': {'chains': [{'chain_ids': ['A'],
                                                                        'molecule_type': 'protein',
                                                                        'sequence': 'MQIFVK'}],
                                                            'use_msas': False}},
                                 'seeds': [42]},
               'inputs': {'queries.json': 'queries mapping; each query has chains with molecule_type, '
                                          'chain_ids and sequence or smiles; top-level seeds'},
               'invocation': {'argv': ['run_openfold',
                                       'predict',
                                       '--query_json=queries.json',
                                       '--output-dir',
                                       'out',
                                       '--use-msa-server',
                                       'false',
                                       '--use-templates',
                                       'false']},
               'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use the '
                                      'configured server documentation.',
               'outputs': ['Model CIF files',
                           'confidences.json',
                           'confidences_aggregated.json',
                           'timing.json'],
               'purpose': 'Protein, nucleic-acid and ligand complex prediction',
               'runtime_tested': False,
               'software': ['OpenFold3'],
               'source': {'path': 'skills/openfold3/SKILL.md',
                          'release': '0.1.60',
                          'sha256': 'eef2b03a2c7e1c4b94cd29bb27f3e02499a77be5c414a494f3d78e9c7cc443de'},
               'status': 'recipe_prepared'},
 'proteinmpnn': {'assets': ['ProteinMPNN repository model checkpoints'],
                 'inputs': {'backbone.pdb': 'Backbone coordinates',
                            'pdb_path_chains': 'Chains selected for design'},
                 'invocation': {'argv': ['python',
                                         'protein_mpnn_run.py',
                                         '--pdb_path',
                                         'backbone.pdb',
                                         '--pdb_path_chains',
                                         'A',
                                         '--out_folder',
                                         'out',
                                         '--num_seq_per_target',
                                         '16',
                                         '--sampling_temp',
                                         '0.1'],
                                'working_directory': 'ProteinMPNN repository'},
                 'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use '
                                        'the configured server documentation.',
                 'outputs': ['Designed amino-acid sequences and scores'],
                 'purpose': 'Backbone-conditioned protein sequence design',
                 'runtime_tested': False,
                 'software': ['dauparas/ProteinMPNN at 8907e6671bfbfc92303b5f79c4b5e6ce47cdef57'],
                 'source': {'path': 'skills/proteinmpnn/SKILL.md',
                            'release': '0.1.60',
                            'sha256': '42b01be755d4feb92820b95712016534d944c168a689c495fc6ab044c16cb7da'},
                 'status': 'recipe_prepared'},
 'scgpt': {'assets': ['Compatible scGPT checkpoint directory'],
           'inputs': {'dataset.h5ad': 'AnnData with a gene-name column in var',
                      'gene_col': 'Column name, for example feature_name',
                      'model_dir': 'Directory containing args.json, best_model.pt and vocab.json'},
           'invocation': {'arguments': {'adata': 'AnnData input',
                                        'gene_col': 'feature_name',
                                        'model_dir': 'Configured checkpoint directory',
                                        'use_fast_transformer': False},
                          'python_entry': 'scgpt.tasks.embed_data'},
           'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use the '
                                  'configured server documentation.',
           'notes': ['The shipped metadata does not establish a reusable license for every separately '
                     'downloaded checkpoint'],
           'outputs': ['AnnData.obsm[X_scGPT]'],
           'purpose': 'Single-cell embeddings and annotation support',
           'runtime_tested': False,
           'software': ['scgpt', 'anndata'],
           'source': {'path': 'skills/scgpt/SKILL.md',
                      'release': '0.1.60',
                      'sha256': 'cfc7161b3dccb7fe2ac7d46642b649a209c4eaddf9512f4faae27d36eb29bc97'},
           'status': 'recipe_prepared'},
 'scvi-tools': {'assets': ['Training data; a pretrained checkpoint is optional for a new scVI fit'],
                'inputs': {'cell_type': 'Reference labels for optional scANVI transfer',
                           'dataset.h5ad': 'AnnData with raw count layer and batch column'},
                'invocation': {'arguments': {'batch_key': 'batch', 'layer': 'counts'},
                               'optional_transfer': 'scvi.model.SCANVI.from_scvi_model',
                               'python_entry': 'scvi.model.SCVI.setup_anndata',
                               'training': {'early_stopping': True,
                                            'max_epochs': 200,
                                            'model': 'scvi.model.SCVI',
                                            'n_latent': 30}},
                'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use '
                                       'the configured server documentation.',
                'notes': ['Preserve raw counts before normalization; batch and label fields must match '
                          'the dataset'],
                'outputs': ['X_scVI latent matrix',
                            'Normalized expression',
                            'Optional X_scANVI and predicted labels'],
                'purpose': 'Single-cell latent representation, batch integration and label transfer',
                'runtime_tested': False,
                'software': ['scvi-tools', 'scanpy', 'anndata'],
                'source': {'path': 'skills/scvi-tools/SKILL.md',
                           'release': '0.1.60',
                           'sha256': '34866479168c8ef7f8e48c2a8e62b35263079af3b749ac35d96ed9748bcfa917'},
                'status': 'recipe_prepared'},
 'solublempnn': {'assets': ['soluble_model_weights/v_48_010 or v_48_020'],
                 'inputs': {'backbone.pdb': 'Protein backbone coordinates',
                            'pdb_path_chains': 'Chains selected for design'},
                 'invocation': {'argv': ['python',
                                         'protein_mpnn_run.py',
                                         '--pdb_path',
                                         'backbone.pdb',
                                         '--pdb_path_chains',
                                         'A',
                                         '--out_folder',
                                         'out',
                                         '--num_seq_per_target',
                                         '16',
                                         '--sampling_temp',
                                         '0.1',
                                         '--use_soluble_model'],
                                'working_directory': 'ProteinMPNN repository'},
                 'model_http_protocol': 'No model-specific HTTP API was observed in this runbook; use '
                                        'the configured server documentation.',
                 'notes': ['Soluble training prior does not establish experimental solubility'],
                 'outputs': ['Designed sequences and scores'],
                 'purpose': 'Backbone-conditioned design with soluble-protein prior',
                 'runtime_tested': False,
                 'software': ['dauparas/ProteinMPNN at 8907e6671bfbfc92303b5f79c4b5e6ce47cdef57'],
                 'source': {'path': 'skills/solublempnn/SKILL.md',
                            'release': '0.1.60',
                            'sha256': 'c2bf64a2e97f500c6fca1814b63bf0ed74aec7dd2212043c86e6003298114bbd'},
                 'status': 'recipe_prepared'}}


def science_model_recipe(model: str = "") -> dict:
    """Read source-anchored input formats and execution recipes for the 14 shipped biological model skills. Does not run inference."""
    if not model:
        return {"source_release": "0.1.60", "models": [{"name": name, "purpose": recipe["purpose"], "status": recipe["status"], "runtime_tested": False} for name, recipe in sorted(_MODEL_RECIPES.items())]}
    if model not in _MODEL_RECIPES:
        raise ValueError("Unknown model. Available: " + ", ".join(sorted(_MODEL_RECIPES)))
    return json.loads(json.dumps({"model": model, **_MODEL_RECIPES[model]}))


def register_tools(mcp) -> None:
    for fn in (science_compute_environment, science_prepare_compute_job, science_capture_compute_result, science_model_endpoint_request, science_model_recipe):
        mcp.tool()(fn)
