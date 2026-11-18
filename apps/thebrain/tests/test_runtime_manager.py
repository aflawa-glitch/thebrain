import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "runtime" / "runtime_manager.py"
spec = importlib.util.spec_from_file_location("runtime_manager", MODULE)
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)


class RuntimeManagerTests(unittest.TestCase):
    def test_platform_key_is_normalized(self):
        self.assertIn("-", rm.platform_key())
        self.assertNotIn(" ", rm.platform_key())

    def test_app_id_rejects_path_traversal(self):
        for bad in ("../escape", "a/b", "", ".", "..", " space"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                rm.app_id(bad)

    def test_app_id_accepts_future_app_names(self):
        self.assertEqual(rm.app_id("app-builder_v2"), "app-builder_v2")

    def test_python_info_detects_current_interpreter(self):
        info = rm.python_info(Path(sys.executable))
        self.assertTrue(info["version"])
        self.assertEqual(info["platform_key"], rm.platform_key())

    def test_manifest_schema_guard(self):
        original = rm.MANIFEST
        try:
            with tempfile.TemporaryDirectory() as tmp:
                rm.MANIFEST = Path(tmp) / "runtime-manifest.json"
                rm.MANIFEST.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    rm.load_manifest()
        finally:
            rm.MANIFEST = original

    def test_missing_managed_runtime_is_explicit_failure(self):
        original = rm.RUNTIMES
        try:
            with tempfile.TemporaryDirectory() as tmp:
                rm.RUNTIMES = Path(tmp) / "runtimes"
                with self.assertRaises(FileNotFoundError):
                    rm.runtime_python()
        finally:
            rm.RUNTIMES = original


    def test_shared_home_can_be_selected_without_project_path_assumptions(self):
        original = (rm.STATE_ROOT, rm.RUNTIMES, rm.ENVS, rm.MANIFEST)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                shared = Path(tmp) / "shared-runtime-home"
                rm.configure_home(str(shared))
                self.assertEqual(rm.STATE_ROOT, shared.resolve())
                self.assertEqual(rm.RUNTIMES, shared.resolve() / "runtimes")
                self.assertEqual(rm.ENVS, shared.resolve() / "envs")
                self.assertEqual(rm.MANIFEST, shared.resolve() / "runtime-manifest.json")
        finally:
            rm.STATE_ROOT, rm.RUNTIMES, rm.ENVS, rm.MANIFEST = original

    def test_create_env_works_at_final_path_and_records_manifest(self):
        original = (rm.STATE_ROOT, rm.RUNTIMES, rm.ENVS, rm.MANIFEST)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp) / "runtime-home"
                rm.configure_home(str(home))
                args = type("Args", (), {"app_id": "test-app", "base_python": sys.executable, "replace": False, "requirements": None})()
                result = rm.cmd_create(args)
                self.assertEqual(result, 0)
                env = home / "envs" / "test-app"
                env_python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                self.assertTrue(env_python.is_file())
                info = rm.python_info(env_python)
                self.assertEqual(Path(info["prefix"]).resolve(), env.resolve())
                manifest = json.loads((home / "runtime-manifest.json").read_text(encoding="utf-8"))
                self.assertTrue(manifest["applications"]["test-app"]["isolation_verified"])
                # A second create must refuse to overwrite the existing environment by default.
                with self.assertRaises(FileExistsError):
                    rm.cmd_create(args)
        finally:
            rm.STATE_ROOT, rm.RUNTIMES, rm.ENVS, rm.MANIFEST = original


if __name__ == "__main__":
    unittest.main()
