import tempfile
from pathlib import Path

import cv2
import numpy as np

from framecraft import format_time, imwrite_unicode, safe_stem


def test_helpers():
    assert format_time(0) == "00:00:00.000"
    assert format_time(3661.234) == "01:01:01.234"
    assert safe_stem('a:b?c*') == "a_b_c_"


def test_lossless_png_roundtrip():
    rng = np.random.default_rng(42)
    frame = rng.integers(0, 256, (48, 64, 3), dtype=np.uint8)
    with tempfile.TemporaryDirectory(prefix="帧影测试_") as folder:
        path = Path(folder) / "中文截图.png"
        imwrite_unicode(path, frame, "png")
        decoded = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        assert decoded is not None
        assert np.array_equal(frame, decoded)


if __name__ == "__main__":
    test_helpers()
    test_lossless_png_roundtrip()
    print("All tests passed")
