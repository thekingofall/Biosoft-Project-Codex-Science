"""Compose existing scientific PNG panels with R grid, preserving their aspect ratios."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from figure_tools import rscript

SCRIPT = Path(__file__).with_name("compose_figure.R")


def _scoped(root: Path, name: str, existing: bool = False) -> Path:
    p = Path(name)
    if not name.strip() or p.is_absolute() or p.drive or ".." in name.replace("\\", "/").split("/"):
        raise ValueError("Panel and output paths must be relative paths within workspace")
    result = (root / p).resolve()
    if result == root or not result.is_relative_to(root):
        raise ValueError("Path must stay within workspace")
    if existing and not result.is_file():
        raise FileNotFoundError(str(result))
    return result


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def _png_info(path: Path) -> dict:
    if path.suffix.lower() != ".png":
        raise ValueError("Panels must be PNG files")
    if path.stat().st_size > 30_000_000:
        raise ValueError("Each PNG must be smaller than 30 MB")
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("Panel is not a valid PNG header")
    width, height = struct.unpack(">II", header[16:24])
    if width < 1 or height < 1 or width * height > 40_000_000:
        raise ValueError("PNG dimensions exceed the panel limit")
    return {"width_px": width, "height_px": height, "sha256": _sha(path)}


def science_compose_figure(workspace: str, panels: list[str], output_prefix: str,
                           outline: list[dict] | None = None, columns: int = 2,
                           rows: int = 0, width_mm: float = 180, height_mm: float = 140,
                           panel_letters: bool = True, gap_mm: float = 3,
                           letter_size_pt: float = 14) -> dict:
    """Arrange PNG panels with R grid and save PNG, PDF and provenance JSON.

    outline optionally supplies one zero-based {column,row,column_span,row_span}
    rectangle per panel on a 12-column grid. Otherwise use a regular rows/columns
    layout. Automatic A..Z labels use Arial; embedded panel text retains its source
    styling. Existing output files are preserved. No image is cropped or stretched.
    """
    root = Path(workspace).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("workspace must be an existing directory")
    if not isinstance(panels, list) or not 1 <= len(panels) <= 26 or any(not isinstance(p, str) for p in panels):
        raise ValueError("Provide between 1 and 26 PNG panel paths")
    for name, value, lower, upper in (("width_mm", width_mm, 40, 400), ("height_mm", height_mm, 40, 400), ("gap_mm", gap_mm, 0, 15), ("letter_size_pt", letter_size_pt, 8, 30)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} must be between {lower} and {upper}")
    if type(panel_letters) is not bool:
        raise ValueError("panel_letters must be boolean")
    if type(rows) is not int or not 0 <= rows <= 26:
        raise ValueError("rows must be an integer between 0 and 26")
    if outline is not None:
        if not isinstance(outline, list) or len(outline) != len(panels):
            raise ValueError("outline must have one rectangle per panel")
        layout = []
        for item in outline:
            if not isinstance(item, dict) or set(item) - {"column", "row", "column_span", "row_span"} or not {"column", "row"} <= set(item):
                raise ValueError("Each rectangle needs column and row, with optional column_span and row_span")
            cell = {"column": item["column"], "row": item["row"], "column_span": item.get("column_span", 1), "row_span": item.get("row_span", 1)}
            if any(type(v) is not int for v in cell.values()) or min(cell["column"], cell["row"]) < 0 or min(cell["column_span"], cell["row_span"]) < 1 or cell["column"] + cell["column_span"] > 12 or cell["row"] + cell["row_span"] > 26:
                raise ValueError("Outline rectangle is outside the 12-column / 26-row grid")
            layout.append(cell)
        grid_columns = 12
        used_rows = max(p["row"] + p["row_span"] for p in layout)
        grid_rows = rows or used_rows
        if grid_rows < used_rows:
            raise ValueError("Outline exceeds the requested rows")
    else:
        if type(columns) is not int or not 1 <= columns <= 12:
            raise ValueError("columns must be an integer between 1 and 12")
        grid_columns = columns
        grid_rows = rows or math.ceil(len(panels) / columns)
        if grid_rows * columns < len(panels):
            raise ValueError("Grid has fewer cells than panels")
        layout = [{"column": i % columns, "row": i // columns, "column_span": 1, "row_span": 1} for i in range(len(panels))]
    for i, a in enumerate(layout):
        for b in layout[i + 1:]:
            if a["column"] < b["column"] + b["column_span"] and b["column"] < a["column"] + a["column_span"] and a["row"] < b["row"] + b["row_span"] and b["row"] < a["row"] + a["row_span"]:
                raise ValueError("Panel rectangles overlap")
    label_height_mm = letter_size_pt * 25.4 / 72 * 1.3 if panel_letters else 0
    for box in layout:
        if width_mm * box["column_span"] / grid_columns - gap_mm <= 3 or height_mm * box["row_span"] / grid_rows - gap_mm - label_height_mm <= 3:
            raise ValueError("Panel cells are too small; enlarge the figure or reduce rows/gaps/letters")
    paths = [_scoped(root, panel, True) for panel in panels]
    records = [{"path": str(p.relative_to(root)), **_png_info(p)} for p in paths]
    if sum(p["width_px"] * p["height_px"] for p in records) > 40_000_000:
        raise ValueError("Combined panels exceed 40 million pixels")
    prefix = _scoped(root, output_prefix)
    outputs = {kind: Path(str(prefix) + "." + kind) for kind in ("png", "pdf", "json")}
    if any(p.exists() for p in outputs.values()):
        raise FileExistsError("Choose a new output prefix; an output already exists")
    # All rendering intermediates stay in the configured task temporary area.
    parent = os.environ.get("CODEX_SCIENCE_TEST_TMP") or os.environ.get("CODEX_SCIENCE_TMP")
    if not parent and os.name == "nt":
        parent = "D:/CodexTmp/Codex/science-composition"
    if parent:
        Path(parent).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="figure-", dir=parent) as temp:
        staging = Path(temp)
        params = {"panels": [{"path": str(path), **box} for path, box in zip(paths, layout)], "columns": grid_columns, "rows": grid_rows, "width_mm": width_mm, "height_mm": height_mm, "gap_mm": gap_mm, "font": "Arial", "letter_size_pt": letter_size_pt, "label_height_mm": label_height_mm, "panel_letters": panel_letters, "output_prefix": str(staging / "composite")}
        config = staging / "params.json"
        config.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ)
        if os.name == "nt":
            env.update(LC_ALL="C", LANG="C")
        result = subprocess.run([rscript(), "--vanilla", str(SCRIPT), str(config)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env)
        if result.returncode:
            raise RuntimeError("R figure composition failed: " + result.stderr[-3000:])
        rendered = {k: staging / ("composite." + k) for k in ("png", "pdf")}
        for kind, path in rendered.items():
            if not path.is_file() or path.stat().st_size < 100:
                raise RuntimeError("R did not produce the expected " + kind)
        for path, record in zip(paths, records):
            if _sha(path) != record["sha256"]:
                raise RuntimeError("A source panel changed during composition")
        manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "engine": "R grid + png", "script_sha256": _sha(SCRIPT), "panels": records, "layout": layout, "columns": grid_columns, "rows": grid_rows, "width_mm": width_mm, "height_mm": height_mm, "dpi": 300, "gap_mm": gap_mm, "panel_letters": panel_letters, "letter_font": "Arial", "letter_size_pt": letter_size_pt, "aspect_ratio": "preserved", "source_panel_typography": "unchanged; inspect source panels for English labels and Arial", "outputs": {k: {"path": str(outputs[k].relative_to(root)), "sha256": _sha(p), "bytes": p.stat().st_size} for k, p in rendered.items()}}
        prefix.parent.mkdir(parents=True, exist_ok=True)
        for kind, source in rendered.items():
            with source.open("rb") as inp, outputs[kind].open("xb") as out:
                shutil.copyfileobj(inp, out)
        with outputs["json"].open("x", encoding="utf-8") as out:
            json.dump(manifest, out, ensure_ascii=False, indent=2)
    return {"files": {k: str(p) for k, p in outputs.items()}, "panel_count": len(panels), "engine": "R", "aspect_ratio": "preserved", "warnings": result.stderr[-1500:]}


def register_tools(mcp) -> None:
    mcp.tool()(science_compose_figure)
