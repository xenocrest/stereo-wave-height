"""Derive WASS text configs from a real generated reference with explicit overrides."""

from __future__ import annotations

from pathlib import Path
import re


SETTING = re.compile(r"^(#?)([A-Z][A-Z0-9_]*)=(.*)$")


def derive_wass_config(
    reference: str | Path,
    destination: str | Path,
    *,
    overrides: dict[str, str | int | float | bool],
) -> Path:
    """Copy a generated config and activate only named, existing settings."""
    source = Path(reference)
    lines = source.read_text(encoding="utf-8").splitlines()
    found: set[str] = set()
    output: list[str] = []
    for line in lines:
        match = SETTING.match(line.strip())
        if match and match.group(2) in overrides:
            key = match.group(2)
            raw = overrides[key]
            value = str(raw).lower() if isinstance(raw, bool) else str(raw)
            output.append(f"{key}={value}")
            found.add(key)
        else:
            output.append(line)
    missing = set(overrides) - found
    if missing:
        raise ValueError(f"override keys absent from generated reference config: {sorted(missing)}")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(output) + "\n", encoding="utf-8")
    return target
