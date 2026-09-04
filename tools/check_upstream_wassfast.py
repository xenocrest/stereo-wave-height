"""Run an isolated upstream network contract check, NOT a measurement test.

Use the dedicated WASSfast virtual environment. No project reconstruction or
GUI modules are imported; architecture and weights come from installed upstream.
"""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    import numpy as np
    import tensorflow as tf
    import wassfast
    from wassfast.cnn.wavenet_models import create_model_with_prediction

    base = Path(wassfast.__file__).parent / "cnn" / "modeldata"
    sparse = base / "2021-06-30_16-48-27.h5"
    complete = base / "2021-07-01_12-00-44_3.h5"
    start = time.perf_counter()
    model = create_model_with_prediction(256, sparsecnn_weights=str(sparse))
    model.load_weights(str(complete))
    load_seconds = time.perf_counter() - start

    # Zero-valued artificial input checks execution only. Identity phase factors
    # are NOT claimed to represent any real wave or project capture geometry.
    data = np.zeros((1, 256, 256, 3), dtype=np.float32)
    phase = np.zeros((1, 256, 256, 4), dtype=np.float32)
    phase[..., 0] = phase[..., 2] = 1
    start = time.perf_counter()
    result = model([data, phase], training=False).numpy()
    seconds = time.perf_counter() - start
    if result.shape != (1, 256, 256, 1) or not np.isfinite(result).all():
        raise ValueError("Upstream output failed shape/finite contract")
    report = {
        "status": "UPSTREAM_NETWORK_CONTRACT_PASS_NOT_PHYSICAL_VALIDATION",
        "versions": {name: importlib.metadata.version(name) for name in
                     ("wassfast", "tensorflow", "keras", "numpy", "opencv-python")},
        "weights": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in (sparse, complete)],
        "devices": [str(device) for device in tf.config.list_physical_devices()],
        "model_load_seconds": load_seconds,
        "inference_seconds": seconds,
        "input": "artificial all-zero full-support grid; identity phase",
        "output_shape": list(result.shape),
        "output_finite_count": int(np.isfinite(result).sum()),
        "output_min": float(result.min()), "output_max": float(result.max()),
        "height_unit": "NOT_ASSIGNED_CONTRACT_TEST_ONLY",
        "official_dataset_reproduction": "NOT_RUN",
        "project_video_reconstruction": "NOT_RUN",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
