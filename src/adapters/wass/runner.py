"""Fail-fast external-process runner for an explicitly bound WASS runtime."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import shutil
from typing import Sequence

from .runtime import WassRuntimeBinding


@dataclass(frozen=True)
class WassExecutables:
    """Backward-compatible native paths to the four WASS core executables."""

    prepare: Path
    match: Path
    autocalibrate: Path
    stereo: Path

    def __post_init__(self) -> None:
        for name, path in (("prepare", self.prepare), ("match", self.match),
                           ("autocalibrate", self.autocalibrate), ("stereo", self.stereo)):
            if not Path(path).is_file():
                raise FileNotFoundError(f"WASS {name} executable not found: {path}")

    def as_runtime(self) -> WassRuntimeBinding:
        """Convert legacy native paths to the explicit runtime model."""
        return WassRuntimeBinding(
            environment_type="native",
            executables={
                "prepare": str(self.prepare),
                "match": str(self.match),
                "autocalibrate": str(self.autocalibrate),
                "stereo": str(self.stereo),
            },
        )


class WassStageError(RuntimeError):
    """A WASS process returned a non-zero status."""

    def __init__(self, stage: str, returncode: int, frame_id: str | None) -> None:
        self.stage = stage
        self.returncode = returncode
        self.frame_id = frame_id
        label = f" frame {frame_id}" if frame_id is not None else ""
        super().__init__(f"WASS stage {stage}{label} failed with return code {returncode}")


@dataclass(frozen=True)
class WassRunResult:
    """Successful run summary."""

    workspace: Path
    completed_stages: tuple[str, ...]
    frame_count: int


class WassRunner:
    """Invoke prepare, match, autocalibrate, and stereo without a shell."""

    def __init__(self, runtime: WassRuntimeBinding | WassExecutables) -> None:
        self.runtime = runtime.as_runtime() if isinstance(runtime, WassExecutables) else runtime

    def _execute(
        self,
        command: Sequence[str],
        *,
        stage: str,
        workspace: Path,
        frame_id: str | None,
    ) -> None:
        label = f"_{frame_id}" if frame_id is not None else ""
        log_dir = workspace / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "stage": stage,
            "frame_id": frame_id,
            "environment_type": self.runtime.environment_type,
            "argv": list(command),
        }
        with (log_dir / "commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        completed = subprocess.run(
            list(command),
            cwd=self.runtime.working_directory or workspace,
            env=self.runtime.process_environment(),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        (log_dir / f"{stage}{label}.stdout.log").write_text(completed.stdout, encoding="utf-8")
        (log_dir / f"{stage}{label}.stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise WassStageError(stage, completed.returncode, frame_id)

    def _command(self, stage: str, arguments: list[str]) -> list[str]:
        return self.runtime.command(stage, arguments)

    def run(self, workspace_root: str | Path) -> WassRunResult:
        """Run the documented WASS sequence for every prepared frame."""
        workspace = Path(workspace_root).resolve()
        manifest_path = workspace / "wass_input_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        frames = manifest.get("frames")
        if not isinstance(frames, list) or not frames:
            raise ValueError("WASS input manifest has no frames")
        matcher_config = workspace / manifest["config"]["matcher_config.txt"]["path"]
        stereo_config = workspace / manifest["config"]["stereo_config.txt"]["path"]
        calibration_dir = workspace / "config"

        for frame in frames:
            frame_id = frame["frame_id"]
            workdir = workspace / frame["workdir"]
            if workdir.exists():
                raise FileExistsError(f"prepare workdir already exists: {workdir}")
            self._execute(
                self._command("prepare", [
                    "--workdir", str(workdir), "--calibdir", str(calibration_dir),
                    "--c0", str(workspace / frame["cam0"]), "--c1", str(workspace / frame["cam1"]),
                ]),
                stage="prepare", workspace=workspace, frame_id=frame_id,
            )
        for frame in frames:
            self._execute(
                self._command("match", [str(matcher_config), str(workspace / frame["workdir"])]),
                stage="match", workspace=workspace, frame_id=frame["frame_id"],
            )

        workdirs_file = workspace / "workdirs.txt"
        workdirs_file.write_text(
            "\n".join(str(workspace / frame["workdir"]) for frame in frames) + "\n",
            encoding="utf-8",
        )
        self._execute(
            self._command("autocalibrate", [str(workdirs_file)]),
            stage="autocalibrate", workspace=workspace, frame_id=None,
        )
        for frame in frames:
            self._execute(
                self._command("stereo", [str(stereo_config), str(workspace / frame["workdir"])]),
                stage="stereo", workspace=workspace, frame_id=frame["frame_id"],
            )
        return WassRunResult(workspace, ("prepare", "match", "autocalibrate", "stereo"), len(frames))

    def run_fixed_calibration(self, workspace_root: str | Path) -> WassRunResult:
        """Run prepare/match/stereo while preserving caller-supplied fixed R/T.

        ``wass_match`` remains a correspondence diagnostic but may write pose
        files.  The verified ``ext_R.xml`` and ``ext_T.xml`` are therefore
        restored into every workdir before stereo.  Autocalibration is never
        invoked by this method.
        """
        workspace = Path(workspace_root).resolve()
        manifest_path = workspace / "wass_input_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        frames = manifest.get("frames")
        if not isinstance(frames, list) or not frames:
            raise ValueError("WASS input manifest has no frames")
        if manifest.get("fixed_calibration_available") is not True:
            raise ValueError("fixed-calibration run requires verified ext_R.xml and ext_T.xml")
        matcher_config = workspace / manifest["config"]["matcher_config.txt"]["path"]
        stereo_config = workspace / manifest["config"]["stereo_config.txt"]["path"]
        calibration_dir = workspace / "config"

        for frame in frames:
            frame_id = frame["frame_id"]
            workdir = workspace / frame["workdir"]
            if workdir.exists():
                raise FileExistsError(f"prepare workdir already exists: {workdir}")
            self._execute(
                self._command("prepare", [
                    "--workdir", str(workdir), "--calibdir", str(calibration_dir),
                    "--c0", str(workspace / frame["cam0"]), "--c1", str(workspace / frame["cam1"]),
                ]),
                stage="prepare", workspace=workspace, frame_id=frame_id,
            )
        for frame in frames:
            frame_id = frame["frame_id"]
            workdir = workspace / frame["workdir"]
            self._execute(
                self._command("match", [str(matcher_config), str(workdir)]),
                stage="match", workspace=workspace, frame_id=frame_id,
            )
            for name in ("ext_R.xml", "ext_T.xml"):
                shutil.copy2(calibration_dir / name, workdir / name)
        for frame in frames:
            self._execute(
                self._command("stereo", [str(stereo_config), str(workspace / frame["workdir"])]),
                stage="stereo", workspace=workspace, frame_id=frame["frame_id"],
            )
        return WassRunResult(workspace, ("prepare", "match", "stereo"), len(frames))
