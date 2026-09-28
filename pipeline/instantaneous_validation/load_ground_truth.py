from __future__ import annotations

import csv
from pathlib import Path

import yaml


def load_truth(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"timestamp", "sensor_id", "x", "y", "quality_flag"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"ground truth CSV missing columns: {sorted(required - set(reader.fieldnames or []))}")
        if "H_true_mm" not in reader.fieldnames and "Z_true_mm" not in reader.fieldnames:
            raise ValueError("ground truth CSV requires H_true_mm or Z_true_mm")
        rows = []
        for row in reader:
            for key in ("timestamp", "x", "y"):
                row[key] = float(row[key])
            for key in ("H_true_mm", "Z_true_mm"):
                if row.get(key):
                    row[key] = float(row[key])
            rows.append(row)
    return rows


def load_layout(path: str | Path) -> dict[str, dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sensors = data.get("sensors", []) if isinstance(data, dict) else []
    if not sensors:
        raise ValueError("sensor_layout requires at least one measured sensor position")
    result = {}
    for sensor in sensors:
        key = str(sensor["id"])
        if key in result:
            raise ValueError(f"duplicate sensor ID: {key}")
        result[key] = sensor
        for coordinate in ("x_mm", "y_mm"):
            value = sensor.get(coordinate)
            if value is None or value == "TBD_AFTER_HARDWARE_ARRIVAL":
                raise ValueError(f"{key}.{coordinate} is not measured")
            float(value)
    return result
