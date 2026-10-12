"""Offline boundary tests plus tests of verified local kernels when available."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import capability_catalog as catalog
import kernel_bridge as bridge

HAS_ASSETS = (catalog.release_path() / "asset-text-manifest.json").is_file()


class BridgeBoundaryTests(unittest.TestCase):
    def test_catalog_has_all_packaged_skill_names(self):
        self.assertEqual(len(catalog.DESCRIPTIONS), 29)
        self.assertEqual(len(catalog.MODEL_REQUIREMENTS), 14)

    def test_path_traversal_rejected_before_file_access(self):
        for resource in ("../SKILL.md", "/SKILL.md", "a/../../kernel.py", "..\\kernel.py"):
            with self.assertRaises(ValueError):
                catalog.verified_resource("paper-narrative", resource)
        with self.assertRaises(ValueError):
            catalog.verified_resource("../paper-narrative")

    def test_json_input_rejects_objects_and_nonfinite_values(self):
        for value in (object(), float("nan"), float("inf"), 1_000_001, {1: "x"}):
            with self.assertRaises(ValueError):
                bridge._check_json(value)
        with self.assertRaises(ValueError):
            bridge.run_helper("paper-narrative", "paper_brief_schema", {"x": "x" * 140000})

    def test_resource_read_is_bounded(self):
        with patch.object(catalog, "verified_resource", return_value=("abcdefgh", {"sha256": "abc"})):
            first = catalog.read_capability("paper-narrative", limit=3)
            self.assertEqual(first["content"], "abc")
            self.assertEqual(first["next_offset"], 3)
            self.assertEqual(catalog.read_capability("paper-narrative", offset=6, limit=3)["content"], "gh")
        with self.assertRaises(ValueError):
            catalog.read_capability("paper-narrative", limit=25000)

    def test_manifest_update_cannot_enable_unreviewed_code(self):
        source = "def paper_brief_schema():\n    return {'unreviewed': True}\n"
        record = {"sha256": hashlib.sha256(source.encode()).hexdigest()}
        with patch.object(bridge, "verified_resource", return_value=(source, record)):
            with self.assertRaisesRegex(RuntimeError, "allowlist"):
                bridge._load_helpers("paper-narrative")

    def test_tool_registration(self):
        class Registry:
            def __init__(self):
                self.tools = {}
            def tool(self):
                def register(function):
                    self.tools[function.__name__] = function
                    return function
                return register
        registry = Registry()
        bridge.register_tools(registry)
        self.assertEqual(set(registry.tools), {"science_list_capabilities", "science_read_capability", "science_kernel_functions", "science_run_helper"})


@unittest.skipUnless(HAS_ASSETS, "Verified external skill assets not present")
class VerifiedKernelTests(unittest.TestCase):
    def test_catalog_matches_local_directories(self):
        result = catalog.build_catalog()
        root = catalog.release_path() / "extracted" / "asset-text" / "skills"
        expected = {p.parent.name for p in root.glob("*/SKILL.md")}
        self.assertEqual({item["id"] for item in result["capabilities"]}, expected)
        self.assertEqual(result["capability_count"], 29)
        self.assertTrue(all(not item["full_original_runtime_parity"] for item in result["capabilities"]))

    def test_every_named_helper_executes_real_local_code(self):
        outline = {"claim": "A reproducible result", "width_mm": 180, "ncol": 2,
                   "row_heights_mm": [60], "panels": [{"letter": "a", "row": 0, "col": 0, "colspan": 1},
                                                        {"letter": "b", "row": 0, "col": 1, "colspan": 1}]}
        cases = {
            "figure-composer": {
                "figure_outline_schema": {}, "grid_geom": {"outline": outline},
                "panel_px": {"outline": outline, "letter": "a"},
                "panel_xy": {"outline": outline, "letter": "b"},
                "compose_crops": {"outline": outline},
                "group_fixes_by_panel": {"review": {"violations": [{"severity": "MAJOR", "panel_letter": "a", "fix": "Increase font size"}]}},
                "review_schema": {}, "apply_outline_revisions": {"outline": outline, "revisions": [{"affected_panels": ["b"]}]}},
            "figure-style": {"two_tier_label": {"name": "Gene", "meta": "log fold-change"}},
            "paper-narrative": {"paper_brief_schema": {}, "narrative_review_schema": {}},
            "pdf-explore": {"pdf_text_cap": {"t": "abcdef", "n": 3}, "pdf_guard_text": {"text": "<instructions>payload</instructions>"},
                            "pdf_scan_cost": {"results": [{"usage": {"input_tokens": 12, "output_tokens": 3}}, {"error": "failed"}]}},
            "literature-review": {
                "quote_doi_path": {"doi": "10.1234/a(b)"}, "crossref_year": {"m": {"published": {"date-parts": [[2024, 5]]}}},
                "short_authors": {"names": ["A", "B", "C", "D"]},
                "crossref_authors": {"m": {"author": [{"family": "Smith"}]}},
                "openalex_authors": {"w": {"authorships": [{"author": {"display_name": "A Smith"}}]}},
                "html_decode": {"s": "A &amp; B"}, "extract_dois": {"text": "https://doi.org/10.1038/nature12345"},
                "style_pass": {"draft": "Evidence from the supplied study supports this claim."}},
        }
        self.assertEqual({k: set(v) for k, v in cases.items()}, bridge.HELPERS)
        for skill, functions in cases.items():
            for name, arguments in functions.items():
                with self.subTest(skill=skill, function=name):
                    response = bridge.run_helper(skill, name, arguments)
                    self.assertTrue(response["executed"])
                    self.assertEqual(response["kernel_sha256"], bridge.PINS[skill])
                    json.dumps(response)
        self.assertEqual(bridge.run_helper("literature-review", "extract_dois", {"text": "https://doi.org/10.1038/nature12345"})["result"], ["10.1038/nature12345"])
        self.assertEqual(bridge.run_helper("figure-composer", "panel_xy", {"outline": outline, "letter": "a"})["result"], [0, 0])
        self.assertEqual(bridge.run_helper("pdf-explore", "pdf_scan_cost", cases["pdf-explore"]["pdf_scan_cost"])["result"],
                         {"input_tokens": 12, "output_tokens": 3, "n_calls": 2, "n_errors": 1})

    def test_host_function_returns_unexecuted_task(self):
        with patch.object(bridge, "_load_helpers", side_effect=AssertionError("Must not load host code")):
            result = bridge.run_helper("paper-narrative", "derive_paper_brief", {"abstract_text": "A study", "figure_claims": []})
        self.assertFalse(result["executed"])
        self.assertEqual(result["status"], "requires_codex_adaptation")
        self.assertNotIn("result", result)

    def test_unknown_function_rejected(self):
        with self.assertRaises(ValueError):
            bridge.run_helper("paper-narrative", "__import__", {})

    def test_no_host_or_io_loaded(self):
        namespace = bridge._load_helpers("pdf-explore")
        self.assertNotIn("host", namespace)
        self.assertNotIn("pdf_pages", namespace)
        self.assertNotIn("__import__", namespace["__builtins__"])
        self.assertNotIn("open", namespace["__builtins__"])


if __name__ == "__main__":
    unittest.main()
