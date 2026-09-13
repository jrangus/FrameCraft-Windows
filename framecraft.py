from __future__ import annotations

import json
import math
import queue
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QImage, QKeySequence, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget,
)


APP_NAME = "帧影 FrameCraft"
APP_VERSION = "1.1.0"
VIDEO_FILTER = "视频文件 (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.mts *.m2ts *.ts *.flv);;所有文件 (*.*)"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def format_time(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        seconds = 0
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def safe_stem(name: str) -> str:
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if c in invalid else c for c in name).strip(" .")
    return cleaned or "video"


def imwrite_unicode(path: Path, frame: np.ndarray, fmt: str) -> None:
    params = [cv2.IMWRITE_PNG_COMPRESSION, 3] if fmt.lower() == "png" else []
    ok, encoded = cv2.imencode("." + fmt.lower(), frame, params)
    if not ok:
        raise OSError("图像编码失败")
    encoded.tofile(str(path))


@dataclass
class Candidate:
    frame_index: int
    score: float
    preview_bgr: np.ndarray


class DropLabel(QLabel):
    def __init__(self, owner: "FrameCraft") -> None:
        super().__init__("将本地视频拖到这里，或点击右上角“打开视频”")
        self.owner = owner
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName("preview")

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.owner.load_video(Path(url.toLocalFile()))
                event.acceptProposedAction()
                return


class FrameCraft(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} · 原始帧无损导出")
        self.resize(1180, 780)
        self.setMinimumSize(860, 600)

        self.video_path: Optional[Path] = None
        self.output_dir: Optional[Path] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame_count = 0
        self.current_index = 0
        self.fps = 0.0
        self.width = 0
        self.height = 0
        self.current_frame: Optional[np.ndarray] = None
        self.playing = False
        self.scan_thread: Optional[threading.Thread] = None
        self.scan_cancel = threading.Event()
        self.scan_queue: queue.Queue = queue.Queue()
        self.candidates: list[Candidate] = []
        self.candidate_dialog: Optional[QDialog] = None
        self.candidate_preview: Optional[QLabel] = None
        self.candidate_detail: Optional[QLabel] = None
        self.candidate_checks: dict[int, QCheckBox] = {}
        self.candidate_buttons: dict[int, QToolButton] = {}
        self.settings_path = app_dir() / "FrameCraft.settings.json"
        self.settings = self._load_settings()

        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._play_tick)
        self.seek_timer = QTimer(self)
        self.seek_timer.setSingleShot(True)
        self.seek_timer.timeout.connect(self._seek_from_slider)
        self.scan_poll_timer = QTimer(self)
        self.scan_poll_timer.timeout.connect(self._poll_scan_queue)
        self.scan_poll_timer.start(120)

        self._build_ui()
        self._bind_shortcuts()
        if len(sys.argv) > 1:
            candidate = Path(sys.argv[1])
            if candidate.is_file():
                QTimer.singleShot(250, lambda: self.load_video(candidate))

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 14, 18, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("帧影")
        title.setObjectName("title")
        subtitle = QLabel("视频原始帧无损导出")
        subtitle.setObjectName("muted")
        header.addWidget(title)
        header.addWidget(subtitle)
        header.addStretch(1)
        for text, callback, accent in (
            ("使用说明", self.show_help, False),
            ("选择保存位置", self.choose_output_dir, False),
            ("打开视频", self.open_video, True),
        ):
            button = QPushButton(text)
            if accent:
                button.setObjectName("accent")
            button.clicked.connect(callback)
            header.addWidget(button)
        outer.addLayout(header)

        info = QFrame()
        info.setObjectName("panel")
        info_layout = QHBoxLayout(info)
        info_layout.setContentsMargins(14, 9, 14, 9)
        self.file_label = QLabel("尚未打开视频")
        self.meta_label = QLabel("支持 MP4 / MKV / MOV / AVI / WebM 等常见格式")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        info_layout.addWidget(self.file_label, 2)
        info_layout.addWidget(self.meta_label, 3)
        outer.addWidget(info)

        self.preview = DropLabel(self)
        outer.addWidget(self.preview, 1)

        timeline = QHBoxLayout()
        self.time_label = QLabel("00:00:00.000")
        self.time_label.setFixedWidth(105)
        self.duration_label = QLabel("00:00:00.000")
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.duration_label.setFixedWidth(105)
        self.frame_label = QLabel("帧 0 / 0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.frame_label.setMinimumWidth(140)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1)
        self.slider.setEnabled(False)
        self.slider.sliderPressed.connect(self.stop_playback)
        self.slider.valueChanged.connect(self._schedule_seek)
        timeline.addWidget(self.time_label)
        timeline.addWidget(self.slider, 1)
        timeline.addWidget(self.duration_label)
        timeline.addWidget(self.frame_label)
        outer.addLayout(timeline)

        controls = QHBoxLayout()
        for text, callback in (
            ("−1 秒", lambda: self.jump_seconds(-1)),
            ("◀ 上一帧", lambda: self.step_frame(-1)),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            controls.addWidget(button)
        self.play_button = QPushButton("播放")
        self.play_button.clicked.connect(self.toggle_play)
        controls.addWidget(self.play_button)
        for text, callback in (
            ("下一帧 ▶", lambda: self.step_frame(1)),
            ("+1 秒", lambda: self.jump_seconds(1)),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            controls.addWidget(button)
        controls.addStretch(1)
        self.scan_button = QPushButton("智能找精彩帧")
        self.scan_button.clicked.connect(self.show_or_scan_candidates)
        self.scan_button.setEnabled(False)
        controls.addWidget(self.scan_button)
        self.save_button = QPushButton("保存当前帧")
        self.save_button.setObjectName("accent")
        self.save_button.clicked.connect(self.save_current)
        self.save_button.setEnabled(False)
        controls.addWidget(self.save_button)
        self.format_box = QComboBox()
        self.format_box.addItems(["PNG", "TIFF", "BMP"])
        self.format_box.setCurrentText(self.settings.get("format", "PNG"))
        self.format_box.currentTextChanged.connect(self._save_settings)
        controls.addWidget(self.format_box)
        outer.addLayout(controls)

        footer = QHBoxLayout()
        self.status_label = QLabel("就绪 · 全程本地处理，不上传视频")
        self.status_label.setObjectName("muted")
        self.output_label = QLabel("保存位置：打开视频后自动创建“截图”文件夹")
        self.output_label.setObjectName("muted")
        self.output_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(self.status_label, 2)
        footer.addWidget(self.output_label, 3)
        outer.addLayout(footer)

    def _bind_shortcuts(self) -> None:
        shortcuts = (
            ("Ctrl+O", self.open_video), ("Ctrl+S", self.save_current),
            ("Space", self.toggle_play), ("Left", lambda: self.step_frame(-1)),
            ("Right", lambda: self.step_frame(1)), ("Shift+Left", lambda: self.jump_seconds(-1)),
            ("Shift+Right", lambda: self.jump_seconds(1)),
        )
        self.shortcuts = []
        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"format": "PNG", "last_open_dir": ""}

    def _save_settings(self) -> None:
        if hasattr(self, "format_box"):
            self.settings["format"] = self.format_box.currentText()
        try:
            self.settings_path.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择本地视频", self.settings.get("last_open_dir", ""), VIDEO_FILTER)
        if path:
            self.load_video(Path(path))

    def load_video(self, path: Path) -> None:
        self.stop_playback()
        self.scan_cancel.set()
        if self.candidate_dialog is not None:
            self.candidate_dialog.close()
            self.candidate_dialog = None
        self.candidates = []
        self.scan_button.setText("智能找精彩帧")
        if self.cap is not None:
            self.cap.release()
        cap = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            QMessageBox.critical(self, "无法打开", "无法解码这个视频。文件可能损坏，或使用了当前版本不支持的编码。")
            return
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frame_count <= 0 or not math.isfinite(fps) or fps <= 0:
            cap.release()
            QMessageBox.critical(self, "视频信息异常", "未能读取视频的帧数或帧率，暂时无法逐帧定位。")
            return
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            QMessageBox.critical(self, "读取失败", "视频已打开，但无法读取第一帧。")
            return

        self.cap = cap
        self.video_path = path.resolve()
        self.frame_count, self.fps = frame_count, fps
        self.width, self.height = width, height
        self.current_index, self.current_frame = 0, frame
        self.output_dir = self.video_path.parent / "截图"
        self.settings["last_open_dir"] = str(self.video_path.parent)
        self._save_settings()
        codec_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join(chr((codec_int >> (8 * i)) & 0xFF) for i in range(4)).strip() or "未知"
        self.file_label.setText(self.video_path.name)
        self.meta_label.setText(f"{width} × {height}  ·  {fps:.3f} FPS  ·  {codec}  ·  {format_time(frame_count / fps)}")
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(1, frame_count - 1))
        self.slider.blockSignals(False)
        self.slider.setEnabled(True)
        self.save_button.setEnabled(True)
        self.scan_button.setEnabled(True)
        self.output_label.setText(f"保存位置：{self.output_dir}")
        self.status_label.setText("已读取原始解码帧 · 预览缩放不会影响导出尺寸")
        self._set_slider(0)
        self._show_frame(frame)

    def _schedule_seek(self, _value: int) -> None:
        if self.cap is None or self.slider.signalsBlocked():
            return
        self.stop_playback()
        self.seek_timer.start(75)

    def _seek_from_slider(self) -> None:
        self.seek_to(self.slider.value())

    def seek_to(self, target: int) -> None:
        if self.cap is None:
            return
        target = max(0, min(self.frame_count - 1, int(target)))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.status_label.setText(f"无法读取第 {target + 1} 帧")
            return
        actual = int(round(self.cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
        self.current_index = max(0, actual if actual >= 0 else target)
        self.current_frame = frame
        self._set_slider(self.current_index)
        self._show_frame(frame)

    def _set_slider(self, index: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(index)
        self.slider.blockSignals(False)
        self.time_label.setText(format_time(index / self.fps if self.fps else 0))
        self.duration_label.setText(format_time(self.frame_count / self.fps if self.fps else 0))
        self.frame_label.setText(f"帧 {index + 1:,} / {self.frame_count:,}")

    def step_frame(self, delta: int) -> None:
        if self.cap is not None:
            self.stop_playback()
            self.seek_to(self.current_index + delta)

    def jump_seconds(self, seconds: int) -> None:
        if self.cap is not None:
            self.stop_playback()
            self.seek_to(self.current_index + round(seconds * self.fps))

    def toggle_play(self) -> None:
        if self.cap is None:
            return
        if self.playing:
            self.stop_playback()
        else:
            self.playing = True
            self.play_button.setText("暂停")
            self.play_timer.start(max(1, int(1000 / min(self.fps, 60))))

    def _play_tick(self) -> None:
        if not self.playing or self.cap is None:
            return
        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.stop_playback()
            return
        self.current_index = max(0, int(round(self.cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1)
        self.current_frame = frame
        self._set_slider(self.current_index)
        self._show_frame(frame)

    def stop_playback(self) -> None:
        self.playing = False
        self.play_timer.stop()
        if hasattr(self, "play_button"):
            self.play_button.setText("播放")

    def _show_frame(self, frame_bgr: np.ndarray) -> None:
        h, w, channels = frame_bgr.shape
        image = QImage(frame_bgr.data, w, h, channels * w, QImage.Format.Format_BGR888).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.preview.setText("")
        self.preview.setPixmap(pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.current_frame is not None:
            QTimer.singleShot(50, lambda: self._show_frame(self.current_frame) if self.current_frame is not None else None)

    def choose_output_dir(self) -> None:
        initial = str(self.output_dir or (self.video_path.parent if self.video_path else Path.home()))
        chosen = QFileDialog.getExistingDirectory(self, "选择截图保存位置", initial)
        if chosen:
            self.output_dir = Path(chosen)
            self.output_label.setText(f"保存位置：{self.output_dir}")

    def save_current(self) -> None:
        if self.current_frame is None or self.video_path is None:
            return
        try:
            path = self._save_frame(self.current_frame, self.current_index)
            self.status_label.setText(f"已无损保存 {self.width} × {self.height}：{path.name}")
            QApplication.beep()
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def _save_frame(self, frame: np.ndarray, frame_index: int) -> Path:
        if self.video_path is None:
            raise OSError("尚未打开视频")
        if self.output_dir is None:
            self.output_dir = self.video_path.parent / "截图"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        fmt = self.format_box.currentText().lower()
        stamp = format_time(frame_index / self.fps).replace(":", "-").replace(".", "-")
        base = f"{safe_stem(self.video_path.stem)}_f{frame_index + 1:08d}_t{stamp}"
        path = self.output_dir / f"{base}.{fmt}"
        serial = 2
        while path.exists():
            path = self.output_dir / f"{base}_{serial}.{fmt}"
            serial += 1
        imwrite_unicode(path, frame, fmt)
        return path

    def _save_candidate_indices(self, indices: set[int]) -> list[Path]:
        saved: list[Path] = []
        for candidate in self.candidates:
            if candidate.frame_index in indices:
                saved.append(self._save_frame(candidate.preview_bgr, candidate.frame_index))
        return saved

    def save_checked_candidates(self) -> None:
        indices = self._checked_candidate_indices()
        if not indices:
            QMessageBox.information(self.candidate_dialog, "尚未勾选", "请先勾选需要保存的候选帧。")
            return
        self._save_candidate_group(indices)

    def save_all_candidates(self) -> None:
        self._save_candidate_group({item.frame_index for item in self.candidates})

    def _save_candidate_group(self, indices: set[int]) -> None:
        try:
            paths = self._save_candidate_indices(indices)
            self.status_label.setText(f"已批量无损保存 {len(paths)} 张精选帧")
            QMessageBox.information(
                self.candidate_dialog,
                "保存完成",
                f"已保存 {len(paths)} 张图片。\n\n位置：{self.output_dir}",
            )
        except Exception as exc:
            QMessageBox.critical(self.candidate_dialog, "保存失败", str(exc))

    def show_or_scan_candidates(self) -> None:
        if self.candidates:
            self._show_candidates()
        else:
            self.start_smart_scan()

    def start_smart_scan(self) -> None:
        if self.video_path is None or self.scan_thread and self.scan_thread.is_alive():
            return
        self.stop_playback()
        self.scan_cancel.clear()
        while not self.scan_queue.empty():
            try:
                self.scan_queue.get_nowait()
            except queue.Empty:
                break
        self.scan_button.setEnabled(False)
        self.scan_button.setText("正在分析…")
        self.status_label.setText("正在本地分析画面… 0%")
        self.scan_thread = threading.Thread(target=self._scan_worker, daemon=True)
        self.scan_thread.start()

    def _scan_worker(self) -> None:
        assert self.video_path is not None
        cap = cv2.VideoCapture(str(self.video_path), cv2.CAP_FFMPEG)
        if not cap.isOpened():
            self.scan_queue.put(("error", "无法为智能筛选打开视频"))
            return
        sample_count = min(500, self.frame_count)
        indices = np.linspace(0, self.frame_count - 1, sample_count, dtype=np.int64)
        rows: list[tuple[int, float, float, float, float]] = []
        previous_gray: Optional[np.ndarray] = None
        for n, index in enumerate(indices):
            if self.scan_cancel.is_set():
                cap.release()
                return
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            h, w = frame.shape[:2]
            small_w = min(320, w)
            small = cv2.resize(frame, (small_w, max(1, int(h * small_w / w))), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            sharp = math.log1p(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            contrast = float(gray.std())
            exposure = max(0.0, 1.0 - abs(float(gray.mean()) - 128.0) / 128.0)
            saturation = float(cv2.cvtColor(small, cv2.COLOR_BGR2HSV)[:, :, 1].mean())
            motion = float(cv2.absdiff(gray, previous_gray).mean()) if previous_gray is not None else 0.0
            previous_gray = gray
            rows.append((int(index), sharp, contrast, exposure, saturation + motion * 0.35))
            if n % 8 == 0:
                self.scan_queue.put(("progress", int((n + 1) * 100 / sample_count)))
        if not rows:
            cap.release()
            self.scan_queue.put(("error", "没有读到可分析的画面"))
            return

        values = np.array([r[1:] for r in rows], dtype=np.float64)
        normalized = np.zeros_like(values)
        for col in range(values.shape[1]):
            lo, hi = np.percentile(values[:, col], [10, 90])
            normalized[:, col] = np.clip((values[:, col] - lo) / max(hi - lo, 1e-6), 0, 1)
        scores = normalized @ np.array([0.42, 0.20, 0.23, 0.15])
        selected: list[tuple[int, float]] = []
        min_gap = max(1, int(self.fps * 1.5))
        for pos in np.argsort(scores)[::-1]:
            index = rows[int(pos)][0]
            if all(abs(index - existing) >= min_gap for existing, _ in selected):
                selected.append((index, float(scores[int(pos)])))
            if len(selected) >= 8:
                break
        candidates: list[Candidate] = []
        for index, score in sorted(selected):
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if ok and frame is not None:
                candidates.append(Candidate(index, score, frame))
        cap.release()
        self.scan_queue.put(("done", candidates))

    def _poll_scan_queue(self) -> None:
        try:
            while True:
                kind, payload = self.scan_queue.get_nowait()
                if kind == "progress":
                    self.status_label.setText(f"正在本地分析画面… {payload}%")
                elif kind == "error":
                    self.scan_button.setEnabled(True)
                    self.scan_button.setText("智能找精彩帧")
                    self.status_label.setText(str(payload))
                    QMessageBox.critical(self, "分析失败", str(payload))
                elif kind == "done":
                    self.candidates = list(payload)
                    self.scan_button.setEnabled(True)
                    self.scan_button.setText(f"管理精选帧 ({len(self.candidates)})")
                    self.status_label.setText("本地分析完成 · 点击候选只会预览，列表会保留")
                    self._show_candidates()
        except queue.Empty:
            return

    def _show_candidates(self) -> None:
        if not self.candidates:
            QMessageBox.information(self, "没有结果", "没有找到合适的候选画面。")
            return
        if self.candidate_dialog is not None:
            self.candidate_dialog.close()
            self.candidate_dialog.deleteLater()
        dialog = QDialog(self)
        self.candidate_dialog = dialog
        dialog.setWindowTitle("精选帧管理器")
        dialog.resize(1120, 800)
        dialog.setModal(False)
        layout = QVBoxLayout(dialog)
        header = QHBoxLayout()
        title = QLabel(f"精选帧管理器 · {len(self.candidates)} 张")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch(1)
        rescan = QPushButton("重新分析")
        rescan.clicked.connect(self.rescan_candidates)
        header.addWidget(rescan)
        layout.addLayout(header)
        hint = QLabel("点击缩略图可在上方大图和主窗口查看；候选列表不会关闭。勾选后可批量保存或移除。")
        hint.setObjectName("muted")
        layout.addWidget(hint)

        self.candidate_preview = QLabel("点击下方候选帧查看大图")
        self.candidate_preview.setObjectName("managerPreview")
        self.candidate_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.candidate_preview.setMinimumHeight(390)
        layout.addWidget(self.candidate_preview, 1)
        self.candidate_detail = QLabel("")
        self.candidate_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.candidate_detail.setObjectName("muted")
        layout.addWidget(self.candidate_detail)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFixedHeight(190)
        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(4, 4, 4, 4)
        strip_layout.setSpacing(8)
        self.candidate_checks = {}
        self.candidate_buttons = {}
        for candidate in self.candidates:
            h, w, channels = candidate.preview_bgr.shape
            image = QImage(candidate.preview_bgr.data, w, h, channels * w, QImage.Format.Format_BGR888).copy()
            pixmap = QPixmap.fromImage(image).scaled(170, 105, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            card = QFrame()
            card.setObjectName("candidateCard")
            card.setFixedWidth(190)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(5, 5, 5, 5)
            button = QToolButton()
            button.setText(f"{format_time(candidate.frame_index / self.fps)}  ·  第 {candidate.frame_index + 1:,} 帧")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIcon(QIcon(pixmap))
            button.setIconSize(pixmap.size())
            button.setFixedHeight(140)
            button.setProperty("selected", False)
            button.clicked.connect(lambda _checked=False, idx=candidate.frame_index: self._pick_candidate(idx))
            check = QCheckBox("勾选")
            self.candidate_buttons[candidate.frame_index] = button
            self.candidate_checks[candidate.frame_index] = check
            card_layout.addWidget(button)
            card_layout.addWidget(check)
            strip_layout.addWidget(card)
        strip_layout.addStretch(1)
        scroll.setWidget(strip)
        layout.addWidget(scroll)

        actions = QHBoxLayout()
        for text, callback in (
            ("全选", lambda: self._set_all_candidate_checks(True)),
            ("取消全选", lambda: self._set_all_candidate_checks(False)),
            ("移除勾选", self.remove_checked_candidates),
            ("清空列表", self.clear_candidates),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch(1)
        save_checked = QPushButton("保存勾选")
        save_checked.clicked.connect(self.save_checked_candidates)
        actions.addWidget(save_checked)
        save_all = QPushButton("全部保存")
        save_all.setObjectName("accent")
        save_all.clicked.connect(self.save_all_candidates)
        actions.addWidget(save_all)
        layout.addLayout(actions)

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._pick_candidate(self.candidates[0].frame_index)

    def _pick_candidate(self, index: int) -> None:
        self.seek_to(index)
        candidate = next((item for item in self.candidates if item.frame_index == index), None)
        if candidate is None:
            return
        for frame_index, button in self.candidate_buttons.items():
            button.setProperty("selected", frame_index == index)
            button.style().unpolish(button)
            button.style().polish(button)
        if self.candidate_preview is not None:
            h, w, channels = candidate.preview_bgr.shape
            image = QImage(candidate.preview_bgr.data, w, h, channels * w, QImage.Format.Format_BGR888).copy()
            target = self.candidate_preview.size()
            pixmap = QPixmap.fromImage(image).scaled(
                target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.candidate_preview.setPixmap(pixmap)
        if self.candidate_detail is not None:
            self.candidate_detail.setText(
                f"{format_time(index / self.fps)}  ·  第 {index + 1:,} 帧  ·  {self.width} × {self.height}"
            )
        self.status_label.setText("正在预览精选帧 · 管理器中的其他候选仍然保留")

    def _checked_candidate_indices(self) -> set[int]:
        return {index for index, check in self.candidate_checks.items() if check.isChecked()}

    def _set_all_candidate_checks(self, checked: bool) -> None:
        for check in self.candidate_checks.values():
            check.setChecked(checked)

    def remove_checked_candidates(self) -> None:
        indices = self._checked_candidate_indices()
        if not indices:
            QMessageBox.information(self.candidate_dialog, "尚未勾选", "请先勾选需要移除的候选帧。")
            return
        answer = QMessageBox.question(
            self.candidate_dialog,
            "移除候选",
            f"从候选列表移除 {len(indices)} 张画面？\n已保存到磁盘的图片不会被删除。",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.candidates = [item for item in self.candidates if item.frame_index not in indices]
            self._after_candidate_list_changed()

    def clear_candidates(self) -> None:
        answer = QMessageBox.question(
            self.candidate_dialog,
            "清空列表",
            "清空全部精选帧候选？\n已保存到磁盘的图片不会被删除。",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.candidates = []
            self._after_candidate_list_changed()

    def _after_candidate_list_changed(self) -> None:
        if self.candidates:
            self.scan_button.setText(f"管理精选帧 ({len(self.candidates)})")
            self.status_label.setText(f"精选帧列表已更新，现有 {len(self.candidates)} 张")
            self._show_candidates()
        else:
            if self.candidate_dialog is not None:
                self.candidate_dialog.close()
                self.candidate_dialog = None
            self.scan_button.setText("智能找精彩帧")
            self.status_label.setText("精选帧列表已清空，可重新分析")

    def rescan_candidates(self) -> None:
        if self.candidate_dialog is not None:
            self.candidate_dialog.close()
            self.candidate_dialog = None
        self.candidates = []
        self.scan_button.setText("智能找精彩帧")
        self.start_smart_scan()

    def show_help(self) -> None:
        QMessageBox.information(
            self, "使用说明",
            "1. 打开或拖入本地视频，拖动时间轴定位。\n"
            "2. 用左右方向键逐帧微调，Shift+方向键跳转 1 秒。\n"
            "3. Ctrl+S 或“保存当前帧”导出；PNG/TIFF/BMP 均为无损格式。\n"
            "4. “智能找精彩帧”在本机筛选候选画面，无需联网。\n"
            "5. 精选帧管理器中点击只会预览；可勾选、批量保存、移除或清空，关闭后仍可重新打开。\n\n"
            "导出采用视频解码后的当前原始像素尺寸，不截取屏幕、不使用预览图。"
            "视频本身若为有损压缩，截图不会恢复编码前已经丢失的细节。\n\n"
            f"{APP_NAME} {APP_VERSION}",
        )

    def closeEvent(self, event) -> None:
        self.scan_cancel.set()
        self.stop_playback()
        if self.cap is not None:
            self.cap.release()
        event.accept()


STYLE = """
QWidget { background: #0d1117; color: #f0f3f6; font-family: "__FONT_FAMILY__"; font-size: 14px; }
QLabel#title { font-size: 22px; font-weight: 700; }
QLabel#muted { color: #8b949e; font-size: 13px; }
QFrame#panel { background: #161b22; border: 1px solid #30363d; border-radius: 7px; }
QLabel#preview { background: #000; color: #8b949e; border: 1px solid #30363d; font-size: 16px; }
QLabel#managerPreview { background: #000; color: #8b949e; border: 1px solid #30363d; font-size: 16px; }
QFrame#candidateCard { background: #161b22; border: 1px solid #30363d; border-radius: 6px; }
QPushButton { background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 8px 13px; }
QPushButton:hover { background: #30363d; border-color: #8b949e; }
QPushButton:pressed { background: #161b22; }
QPushButton:disabled { color: #6e7681; background: #161b22; }
QToolButton { background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 5px; }
QToolButton:hover { background: #30363d; border-color: #8b949e; }
QPushButton#accent { background: #238636; border-color: #2ea043; color: white; font-weight: 700; }
QPushButton#accent:hover { background: #2ea043; }
QPushButton[selected="true"] { border: 2px solid #2f81f7; background: #1f2d3d; }
QToolButton[selected="true"] { border: 2px solid #2f81f7; background: #1f2d3d; }
QSlider::groove:horizontal { height: 5px; background: #30363d; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #2f81f7; border-radius: 2px; }
QSlider::handle:horizontal { background: #f0f6fc; width: 15px; margin: -5px 0; border-radius: 7px; }
QComboBox { background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 7px 10px; min-width: 70px; }
QComboBox QAbstractItemView { background: #161b22; selection-background-color: #2f81f7; }
QMessageBox, QDialog { background: #0d1117; }
"""


def configure_app(app: QApplication) -> None:
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    font_id = QFontDatabase.addApplicationFont(str(resource_path("assets/NotoSansCJKsc-Regular.otf")))
    font_families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    font_family = font_families[0] if font_families else "Microsoft YaHei UI"
    app.setFont(QFont(font_family, 10))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f0f3f6"))
    app.setPalette(palette)
    app.setStyleSheet(STYLE.replace("__FONT_FAMILY__", font_family))


def main() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    app = QApplication(sys.argv)
    configure_app(app)
    window = FrameCraft()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
