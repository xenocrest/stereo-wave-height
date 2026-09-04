"""Preview pacing must not turn 60 FPS input into half-speed playback."""
import pytest

from application.video_tools import preview_frame_interval


@pytest.mark.parametrize("fps", [24, 30, 60, 59.94])
def test_source_rate_preserved(fps):
    assert preview_frame_interval(fps, 30) == pytest.approx(1 / fps)


@pytest.mark.parametrize("fps", [0, -1, float("nan")])
def test_unknown_rate_rejected(fps):
    with pytest.raises(ValueError):
        preview_frame_interval(fps, 30)
