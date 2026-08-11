"""Fail-fast external-process runner for the locked WASS core pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Sequence


@dataclass(frozen=True)
class WassExecutables:
    """Explicit paths to the four WASS v1.5 core executables."""

    prepare: Path
    match: Path
    autocalibrate: Path
    stereo: Path

    def __post_init__(self) -> None:
        for name, path in (("prepare", self.prepare), ("match", self.match),
                           ("autocalibrate", self.autocalibrate), ("stereo", self.stereo)):
            if not Path(path).is_file():
                raise FileNotFoundError(f"WASS {name} executable not found: {path}")


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

    def __init__(self, executables: WassExecutables) -> None:
        self.executables = executables

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
        record = {"stage": stage, "frame_id": frame_id, "argv": list(command)}
        with (log_dir / "commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        completed = subprocess.run(
            list(command), cwd=workspace, capture_output=True, text=True, check=False, shell=False
        )
        (log_dir / f"{stage}{label}.stdout.log").write_text(completed.stdout, encoding="utf-8")
        (log_dir / f"{stage}{label}.stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise WassStageError(stage, completed.returncode, frame_id)

    def run(self, workspace_root: str | Path) -> WassRunResult:
        """Run the documented WASS v1.5 sequence for every prepared frame."""
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
                [str(self.executables.prepare), "--workdir", str(workdir), "--calibdir",
                 str(calibration_dir), "--c0", str(workspace / frame["cam0"]), "--c1",
                 str(workspace / frame["cam1"])],
                stage="prepare", workspace=workspace, frame_id=frame_id,
            )
        for frame in frames:
            self._execute(
                [str(self.executables.match), str(matcher_config), str(workspace / frame["workdir"])],
                stage="match", workspace=workspace, frame_id=frame["frame_id"],
            )

        workdirs_file = workspace / "workdirs.txt"
        workdirs_file.write_text(
            "\n".join(str(workspace / frame["workdir"]) for frame in frames) + "\n",
            encoding="utf-8",
        )
        self._execute(
            [str(self.executables.autocalibrate), str(workdirs_file)],
            stage="autocalibrate", workspace=workspace, frame_id=None,
        )
        for frame in frames:
            self._execute(
                [str(self.executables.stereo), str(stereo_config), str(workspace / frame["workdir"])],
                stage="stereo", workspace=workspace, frame_id=frame["frame_id"],
            )
        return WassRunResult(workspace, ("prepare", "match", "autocalibrate", "stereo"), len(frames))
