import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import composition_tools as ct


class CompositionTests(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get("CODEX_SCIENCE_TEST_TMP")
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        Image.new("RGB", (400, 200), "#B56B45").save(self.root / "wide.png")
        Image.new("RGB", (200, 400), "#355C7D").save(self.root / "tall.png")

    def compose(self, **kwargs):
        return ct.science_compose_figure(str(self.root), ["wide.png", "tall.png"], "figures/composite", **kwargs)

    def test_rejects_outside_paths(self):
        for path in ["../wide.png", str(self.root / "wide.png"), "."]:
            with self.assertRaises(ValueError):
                ct.science_compose_figure(str(self.root), [path], "figure")
        with self.assertRaises(ValueError):
            ct.science_compose_figure(str(self.root), ["wide.png"], "../outside")

    def test_rejects_overlap_and_grid_overflow(self):
        for outline in [
            [{"column": 0, "row": 0, "column_span": 7}, {"column": 6, "row": 0, "column_span": 6}],
            [{"column": 0, "row": 0}, {"column": 12, "row": 0}],
            [{"column": 0, "row": 0, "row_span": 0}, {"column": 6, "row": 0}],
        ]:
            with self.assertRaises(ValueError):
                self.compose(outline=outline)
        with self.assertRaises(ValueError):
            self.compose(rows=1, columns=1)
        with self.assertRaises(ValueError):
            self.compose(width_mm=float("nan"))

    def test_preserves_existing_outputs(self):
        (self.root / "figures").mkdir()
        p = self.root / "figures/composite.pdf"
        p.write_bytes(b"existing-pdf")
        with self.assertRaises(FileExistsError):
            self.compose()
        self.assertEqual(p.read_bytes(), b"existing-pdf")

    def test_failed_r_run_has_no_deliverables(self):
        with patch.object(ct, "rscript", return_value="Rscript"), patch.object(ct.subprocess, "run", return_value=SimpleNamespace(returncode=1, stderr="fixture failure")):
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                self.compose()
        self.assertFalse((self.root / "figures/composite.json").exists())
        self.assertFalse((self.root / "figures/composite.png").exists())

    def test_rejects_invalid_png(self):
        (self.root / "wide.png").write_bytes(b"not-png")
        with self.assertRaises(ValueError):
            self.compose()

    @unittest.skipUnless(os.environ.get("CODEX_SCIENCE_TEST_R") == "1", "R acceptance is opt-in")
    def test_real_r_exports_and_preserves_aspect(self):
        result = self.compose(width_mm=180, height_mm=120)
        pdf = Path(result["files"]["pdf"])
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
        manifest = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["letter_font"], "Arial")
        self.assertEqual(manifest["panels"][0]["sha256"], hashlib.sha256((self.root / "wide.png").read_bytes()).hexdigest())
        with Image.open(result["files"]["png"]) as im:
            rgb = im.convert("RGB")
            self.assertAlmostEqual(im.width, 180 / 25.4 * 300, delta=2)
            for colour, expected_ratio in [((181, 107, 69), 2.0), ((53, 92, 125), 0.5)]:
                mask = Image.new("1", rgb.size)
                mask.putdata([pixel == colour for pixel in rgb.get_flattened_data()])
                bounds = mask.getbbox()
                self.assertIsNotNone(bounds)
                left, top, right, bottom = bounds
                self.assertAlmostEqual((right - left) / (bottom - top), expected_ratio, delta=0.025)
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(str(pdf)) as doc:
            self.assertEqual(len(doc), 1)
            page = doc[0]
            text = page.get_textpage()
            extracted = text.get_text_range()
            self.assertIn("A", extracted)
            self.assertIn("B", extracted)
            text.close()
            page.close()

    @unittest.skipUnless(os.environ.get("CODEX_SCIENCE_TEST_R") == "1", "R acceptance is opt-in")
    def test_real_twelve_column_outline_without_letters(self):
        result = self.compose(outline=[{"column": 0, "row": 0, "column_span": 8}, {"column": 8, "row": 0, "column_span": 4}], panel_letters=False)
        manifest = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["columns"], 12)
        self.assertFalse(manifest["panel_letters"])
        self.assertEqual(manifest["outputs"]["png"]["sha256"], hashlib.sha256(Path(result["files"]["png"]).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
