"""Explicit, portable binding to an existing external WASS runtime."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Any


CORE_STAGES = ("prepare", "match", "autocalibrate", "stereo")


@dataclass(frozen=True)
class WassRuntimeBinding:
    """External command binding with no implicit path or environment discovery."""

    environment_type: str
    executables: dict[str, str]
    command_prefix: tuple[str, ...] = ()
    environment_variables: tuple[tuple[str, str], ...] = ()
    working_directory: str | None = None
    observed_version: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if self.environment_type not in {"native", "wsl", "docker"}:
            raise ValueError("environment_type must be native, wsl, or docker")
        missing = [stage for stage in CORE_STAGES if not self.executables.get(stage)]
        if missing:
            raise ValueError(f"runtime executable mapping missing: {missing}")
        if self.environment_type == "native":
            absent = [stage for stage in CORE_STAGES if not Path(self.executables[stage]).is_file()]
            if absent:
                raise FileNotFoundError(f"native WASS executables not found for: {absent}")
            if self.working_directory is not None and not Path(self.working_directory).is_dir():
                raise FileNotFoundError(self.working_directory)
        elif not self.command_prefix:
            raise ValueError("wsl/docker bindings require an explicit command_prefix")
        keys = [key for key, _ in self.environment_variables]
        if len(keys) != len(set(keys)) or any(not key for key in keys):
            raise ValueError("environment variable names must be non-empty and unique")

    @property
    def gridsurface(self) -> str | None:
        """Return the explicitly configured gridder path/name, if any."""
        return self.executables.get("gridsurface")

    def command(self, stage: str, arguments: list[str]) -> list[str]:
        """Build argv for one core stage without a shell."""
        if stage not in CORE_STAGES:
            raise ValueError(f"unsupported WASS core stage: {stage}")
        return [*self.command_prefix, self.executables[stage], *arguments]

    def process_environment(self) -> dict[str, str]:
        """Return the inherited environment plus explicitly declared overrides."""
        result = os.environ.copy()
        result.update(dict(self.environment_variables))
        return result


@dataclass(frozen=True)
class RuntimeProbeResult:
    """Observed process-launch result; a CLI may reject ``--help`` and remain callable."""

    stage: str
    argv: tuple[str, ...]
    returncode: int
    banner: str
    callable: bool


def load_runtime_binding(path: str | Path) -> WassRuntimeBinding:
    """Load a JSON runtime binding; no path defaults are supplied."""
    source = Path(path)
    data: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    return WassRuntimeBinding(
        environment_type=str(data["environment_type"]),
        executables={
            str(key): str(value) for key, value in data["executables"].items() if value is not None
        },
        command_prefix=tuple(str(value) for value in data.get("command_prefix", [])),
        environment_variables=tuple(
            (str(key), str(value)) for key, value in data.get("environment_variables", {}).items()
        ),
        working_directory=(str(data["working_directory"]) if data.get("working_directory") else None),
        observed_version=str(data.get("observed_version", "UNKNOWN")),
    )


def probe_core_runtime(binding: WassRuntimeBinding) -> tuple[RuntimeProbeResult, ...]:
    """Launch each core executable with ``--help`` and capture its version banner.

    The observed Windows WASS build rejects ``--help`` with a non-zero code but
    prints its version before argument validation. Callable therefore means the
    process launched and emitted its own stage name, not that return code was 0.
    """
    results: list[RuntimeProbeResult] = []
    for stage in CORE_STAGES:
        argv = binding.command(stage, ["--help"])
        completed = subprocess.run(
            argv,
            cwd=binding.working_directory,
            env=binding.process_environment(),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        banner = (completed.stdout + completed.stderr).strip()
        results.append(
            RuntimeProbeResult(
                stage=stage,
                argv=tuple(argv),
                returncode=completed.returncode,
                banner=banner,
                callable=f"wass_{stage}" in banner,
            )
        )
    return tuple(results)
