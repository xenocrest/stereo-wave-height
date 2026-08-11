"""Tests for explicit native/WSL/Docker WASS runtime bindings."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from adapters.wass.runtime import WassRuntimeBinding, load_runtime_binding, probe_core_runtime


class WassRuntimeTests(unittest.TestCase):
    def test_native_runtime_json_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executables = {}
            for stage in ("prepare", "match", "autocalibrate", "stereo"):
                path = root / f"wass_{stage}.exe"
                path.write_bytes(b"fixture")
                executables[stage] = str(path)
            config = root / "runtime.json"
            config.write_text(json.dumps({
                "environment_type": "native",
                "working_directory": str(root),
                "executables": executables,
                "observed_version": "test-version",
            }), encoding="utf-8")
            binding = load_runtime_binding(config)
            self.assertEqual(binding.environment_type, "native")
            self.assertEqual(binding.observed_version, "test-version")
            self.assertEqual(binding.command("prepare", ["--help"])[-1], "--help")

    def test_wsl_binding_requires_and_uses_explicit_prefix(self) -> None:
        binding = WassRuntimeBinding(
            environment_type="wsl",
            command_prefix=("wsl.exe", "-d", "ExplicitDistro", "--"),
            executables={
                "prepare": "/opt/wass/wass_prepare",
                "match": "/opt/wass/wass_match",
                "autocalibrate": "/opt/wass/wass_autocalibrate",
                "stereo": "/opt/wass/wass_stereo",
            },
        )
        self.assertEqual(
            binding.command("match", ["config", "work"]),
            ["wsl.exe", "-d", "ExplicitDistro", "--", "/opt/wass/wass_match", "config", "work"],
        )

    def test_probe_accepts_observed_banner_despite_help_return_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executables = {}
            for stage in ("prepare", "match", "autocalibrate", "stereo"):
                path = root / f"wass_{stage}.exe"
                path.write_bytes(b"fixture")
                executables[stage] = str(path)
            binding = WassRuntimeBinding("native", executables, working_directory=str(root))

            def completed(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                stage = Path(argv[0]).stem
                return subprocess.CompletedProcess(argv, -1, stdout=f"{stage} v. observed\n", stderr="bad arg")

            with patch("adapters.wass.runtime.subprocess.run", side_effect=completed):
                results = probe_core_runtime(binding)
            self.assertEqual(len(results), 4)
            self.assertTrue(all(result.callable for result in results))
            self.assertTrue(all(result.returncode == -1 for result in results))


if __name__ == "__main__":
    unittest.main()
