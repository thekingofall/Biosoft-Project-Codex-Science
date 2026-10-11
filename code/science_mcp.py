"""Codex stdio entry point for locally extracted Claude Science bio tools."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tomllib

PROJECT = Path(__file__).resolve().parents[1]
RELEASE = Path(os.environ.get('CODEX_SCIENCE_RELEASE', str(PROJECT.parent / '0.1.60'))).expanduser().resolve()
BIO = RELEASE / 'extracted' / 'asset-text' / 'mcp-servers' / 'bio-tools'
ALLOWED_SETTINGS = {'NCBI_EMAIL', 'NCBI_API_KEY', 'OPENALEX_API_KEY'}


def prepare() -> dict:
    # Keep the extracted distribution as the sole source; fail on corruption.
    manifest = RELEASE / 'asset-text-manifest.json'
    if not manifest.is_file():
        raise RuntimeError('Set CODEX_SCIENCE_RELEASE to your prepared Claude Science 0.1.60 release directory; see docs/setup.md.')
    records = json.loads(manifest.read_text(encoding='utf-8'))
    count = 0
    for item in records:
        if not item['name'].startswith('mcp-servers/bio-tools/'):
            continue
        path = (RELEASE / 'extracted' / 'asset-text' / item['name']).resolve()
        if not path.is_relative_to(BIO.resolve()):
            raise ValueError('Unexpected path in extraction manifest')
        data = path.read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise RuntimeError(f'Extracted file changed: {item["name"]}. Restore the verified release before starting.')
        count += 1
    if not count or not (BIO / 'run_server.py').is_file():
        raise RuntimeError('Verified Claude Science 0.1.60 bio-tools assets are missing.')
    settings = PROJECT / 'user-settings.toml'
    if settings.exists():
        config = tomllib.loads(settings.read_text(encoding='utf-8-sig')).get('credentials', {})
        if set(config) - ALLOWED_SETTINGS:
            raise ValueError('Unsupported credential setting; see user-settings.example.toml')
        for key, value in config.items():
            if not isinstance(value, str):
                raise ValueError(f'{key} must be a string')
            if value.strip():
                os.environ.setdefault(key, value.strip())
    os.environ.setdefault('OPERON_VERSION', '0.1.60')
    os.environ.setdefault('PYTHONUTF8', '1')
    domains = json.loads((BIO / 'lib/mcp_bio/domains.json').read_text(encoding='utf-8'))
    gate = json.loads((BIO / 'lib/mcp_bio/deferred.json').read_text(encoding='utf-8'))
    excluded = set(gate.get('tools', []) + gate.get('license_tools', []) + gate.get('unavailable_tools', []))
    for domain in gate.get('domains', []):
        excluded.update(domains[domain])
    return {'source_version': '0.1.60', 'verified_files': count,
            'domains': {name: len(set(names) - excluded) for name, names in domains.items()},
            'tool_count': len({name for names in domains.values() for name in names} - excluded),
            'excluded_count': len(excluded),
            'credentials_configured': {key: bool(os.environ.get(key)) for key in sorted(ALLOWED_SETTINGS)}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify local assets and report configuration without network requests.')
    args = parser.parse_args()
    try:
        status = prepare()
    except Exception as exc:
        print(f'Claude Science Codex setup error: {exc}', file=sys.stderr)
        raise SystemExit(2) from exc
    if args.check:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return
    sys.argv = [str(BIO / 'run_server.py'), 'mcp_bio']
    runpy.run_path(str(BIO / 'run_server.py'), run_name='__main__')


if __name__ == '__main__':
    main()
