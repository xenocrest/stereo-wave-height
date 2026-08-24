"""Command-line entry point for the reconstruction pipeline."""

from __future__ import annotations

import argparse
import json

from .pipeline import ReconstructionPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fixed-calibration WASS reconstruction")
    parser.add_argument("--config", required=True, help="Path to reconstruction YAML configuration")
    args = parser.parse_args()
    result = ReconstructionPipeline.from_file(args.config).run()
    print(json.dumps({
        "status": result.status,
        "frame_count": result.frame_count,
        "point_count": result.point_count,
        "result_json": str(result.result_json),
        "report_markdown": str(result.report_markdown),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
