"""Bounded whole-pair target-time fallback policy for the demo adapter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


T = TypeVar("T")
FALLBACK_FRAME_OFFSETS = (0, -1, 1, -2, 2)


@dataclass(frozen=True)
class FallbackResult(Generic[T]):
    value: T
    frame_offset: int
    actual_time_sec: float
    failures: tuple[str, ...]


def run_bounded_fallback(
    target_time_sec: float,
    frame_period_sec: float,
    attempt: Callable[[float, int], T],
    *,
    should_retry: Callable[[Exception], bool] | None = None,
) -> FallbackResult[T]:
    """Stop at the first success; every candidate shifts the whole synchronized time."""
    if frame_period_sec <= 0:
        raise ValueError("frame_period_sec must be positive")
    failures: list[str] = []
    for offset in FALLBACK_FRAME_OFFSETS:
        candidate=max(0.0,target_time_sec+offset*frame_period_sec)
        try:
            return FallbackResult(attempt(candidate,offset),offset,candidate,tuple(failures))
        except Exception as error:
            if should_retry is not None and not should_retry(error):
                raise
            failures.append(f"offset {offset:+d}: {type(error).__name__}: {error}")
    raise RuntimeError("当前时刻附近连续多帧缺乏足够的双目匹配信息，无法获得可靠三维结果。"
                       f"已尝试 ±{2*frame_period_sec*1000:.1f} ms。建议继续播放一小段后重新暂停测量。\n"+"\n".join(failures))
