import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PySide6.QtWidgets import QApplication

from framecraft import Candidate, FrameCraft, configure_app


def main():
    app = QApplication.instance() or QApplication([])
    configure_app(app)
    with tempfile.TemporaryDirectory(prefix="framecraft_integration_") as temp:
        folder = Path(temp)
        video = folder / "中文测试视频.avi"
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 180))
        expected = []
        for i in range(30):
            frame = np.zeros((180, 320, 3), np.uint8)
            frame[:, :, 0] = i * 5
            frame[:, :, 1] = np.arange(320, dtype=np.uint8)
            frame[:, :, 2] = np.arange(180, dtype=np.uint8)[:, None]
            cv2.putText(frame, f"FRAME {i}", (65, 95), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            expected.append(frame)
            writer.write(frame)
        writer.release()

        window = FrameCraft()
        window.show()
        app.processEvents()
        window.load_video(video)
        window.seek_to(13)
        assert window.current_index == 13
        assert window.current_frame is not None
        assert window.current_frame.shape == (180, 320, 3)
        window.output_dir = folder / "截图"
        window.format_box.setCurrentText("PNG")
        decoded_frame = window.current_frame.copy()
        window.save_current()
        output = next(window.output_dir.glob("*.png"))
        saved = cv2.imdecode(np.fromfile(str(output), np.uint8), cv2.IMREAD_UNCHANGED)
        assert np.array_equal(decoded_frame, saved), "PNG round trip changed pixels"

        window.seek_to(5)
        first_candidate_frame = window.current_frame.copy()
        window.seek_to(13)
        window.candidates = [
            Candidate(5, 0.9, first_candidate_frame),
            Candidate(13, 0.8, window.current_frame.copy()),
        ]
        window._show_candidates()
        app.processEvents()
        assert window.candidate_dialog is not None and window.candidate_dialog.isVisible()
        window._pick_candidate(5)
        app.processEvents()
        assert window.current_index == 5
        assert len(window.candidates) == 2
        assert window.candidate_dialog.isVisible(), "clicking a candidate closed the manager"
        assert window.candidate_preview.pixmap() is not None
        window._set_all_candidate_checks(True)
        assert window._checked_candidate_indices() == {5, 13}
        batch_paths = window._save_candidate_indices({5, 13})
        assert len(batch_paths) == 2 and all(path.exists() for path in batch_paths)

        screenshot = Path(__file__).parent / "ui-preview.png"
        assert window.grab().save(str(screenshot), "PNG")
        assert screenshot.stat().st_size > 10_000
        manager_screenshot = Path(__file__).parent / "manager-preview.png"
        assert window.candidate_dialog.grab().save(str(manager_screenshot), "PNG")
        assert manager_screenshot.stat().st_size > 10_000
        print({
            "frame": window.current_index,
            "resolution": list(saved.shape),
            "pixel_equal": bool(np.array_equal(decoded_frame, saved)),
            "manager_stays_open": window.candidate_dialog.isVisible(),
            "batch_saved": len(batch_paths),
            "ui_screenshot": str(screenshot),
            "manager_screenshot": str(manager_screenshot),
        })
        window.close()


if __name__ == "__main__":
    main()
