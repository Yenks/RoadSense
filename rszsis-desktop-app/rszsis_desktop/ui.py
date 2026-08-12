from __future__ import annotations

import csv
from pathlib import Path

from PyQt6.QtCore import QDate, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QTextDocument
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDateEdit, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSlider, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

from .auth import AuthError, AuthManager
from .paths import add_pipeline_to_path, calibration_path_for, ensure_packaged_runtime_paths
from .processing import ProcessingWorker, read_video_metadata
from .sync import SyncManager

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}

STYLE = """
QMainWindow, QWidget { background: #101820; color: #e7edf3; font-family: Segoe UI, Inter, Arial; }
#Sidebar { background: #0b1118; border-right: 1px solid #23303b; }
#Brand { color: #ffb14a; font-size: 19px; font-weight: 800; }
#NavButton { text-align: left; padding: 12px 14px; border-radius: 8px; border: 0; color: #cfd8e3; background: transparent; font-weight: 650; }
#NavButton:checked, #NavButton:hover { background: #1b2835; color: #ffffff; }
#SyncBadge, #Badge { padding: 5px 9px; border-radius: 8px; font-weight: 700; }
#Card { background: #15212c; border: 1px solid #273847; border-radius: 8px; }
#Title { font-size: 24px; font-weight: 800; color: #ffffff; }
#SectionTitle { font-size: 15px; font-weight: 800; color: #ffffff; }
#DropZone { border: 2px dashed #4a5e70; border-radius: 8px; background: #111c26; }
#DataValue { font-family: Consolas, Cascadia Mono, monospace; font-size: 22px; font-weight: 800; color: #ffb14a; }
#LoginHint { color: #8fa1b3; }
#LoginError { color: #ff8f8f; font-weight: 700; }
#SuccessText { color: #6be394; font-weight: 700; font-size: 14px; }
#EmptyStateTitle { font-size: 16px; font-weight: 800; color: #cfd8e3; }
#EmptyStateSub { font-size: 13px; color: #7f93a6; }
QPushButton { background: #243241; border: 1px solid #34495a; padding: 9px 12px; border-radius: 8px; color: #e7edf3; font-weight: 700; }
QPushButton:hover { background: #2b3c4d; }
QPushButton#Primary { background: #ff9f1c; color: #151a1f; border-color: #ffb14a; }
QPushButton#Primary:hover { background: #ffb14a; }
QPushButton#Danger { background: #8f2f2f; color: #fff; border-color: #b64040; }
QPushButton#LinkButton { background: transparent; border: none; color: #ffb14a; text-decoration: underline; padding: 4px; font-weight: 650; }
QPushButton#LinkButton:hover { color: #ffd699; }
QPushButton:disabled { background: #1a232c; color: #65717e; border-color: #26313d; }
QLineEdit, QDateEdit, QSpinBox, QDoubleSpinBox { background: #0f1922; border: 1px solid #34495a; border-radius: 7px; padding: 7px; color: #e7edf3; }
QLineEdit:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #ff9f1c; }
QTableWidget { background: #111b24; border: 1px solid #273847; border-radius: 8px; gridline-color: #273847; }
QHeaderView::section { background: #1b2835; color: #fff; padding: 7px; border: 0; font-weight: 800; }
QProgressBar { border: 1px solid #34495a; border-radius: 7px; background: #0f1922; text-align: center; }
QProgressBar::chunk { background: #ff9f1c; border-radius: 6px; }
QSlider::groove:horizontal { height: 5px; background: #34495a; border-radius: 2px; }
QSlider::handle:horizontal { background: #ff9f1c; width: 16px; margin: -6px 0; border-radius: 8px; }
QScrollArea { border: none; background: transparent; }
"""


def card(layout=None) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    frame.setContentsMargins(16, 16, 16, 16)
    if layout is not None:
        frame.setLayout(layout)
    return frame


class LoginWindow(QMainWindow):
    """Supabase Auth email/password gate supporting Sign In, Sign Up, and Email Confirmation."""

    login_succeeded = pyqtSignal()

    def __init__(self, auth: AuthManager):
        super().__init__()
        self.auth = auth
        self.mode = "login"  # "login", "signup", or "confirm_success"
        self.setWindowTitle("RSZSIS Desktop — Authentication")
        self.setMinimumSize(480, 500)
        self.resize(500, 560)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(14)

        self.brand = QLabel("RSZSIS Desktop")
        self.brand.setObjectName("Brand")
        self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title = QLabel("Sign in")
        self.title.setObjectName("Title")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hint = QLabel("Use your Supabase account credentials.")
        self.hint.setObjectName("LoginHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setWordWrap(True)

        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(10)

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email address")
        self.email.setAccessibleName("Email address")
        self.email.returnPressed.connect(self.handle_submit)

        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName("Password")
        self.password.returnPressed.connect(self.handle_submit)

        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("Confirm password")
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setAccessibleName("Confirm password")
        self.confirm_password.returnPressed.connect(self.handle_submit)

        self.email_label = QLabel("Email")
        self.password_label = QLabel("Password")
        self.confirm_password_label = QLabel("Confirm Password")

        self.form_layout.addRow(self.email_label, self.email)
        self.form_layout.addRow(self.password_label, self.password)
        self.form_layout.addRow(self.confirm_password_label, self.confirm_password)

        self.error = QLabel("")
        self.error.setObjectName("LoginError")
        self.error.setWordWrap(True)
        self.error.hide()

        self.success_msg = QLabel("")
        self.success_msg.setObjectName("SuccessText")
        self.success_msg.setWordWrap(True)
        self.success_msg.hide()

        self.submit = QPushButton("Log In")
        self.submit.setObjectName("Primary")
        self.submit.clicked.connect(self.handle_submit)

        self.toggle_btn = QPushButton("Create an account")
        self.toggle_btn.setObjectName("LinkButton")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_mode)

        self.form_card = card(QVBoxLayout())
        self.form_card.layout().addLayout(self.form_layout)
        self.form_card.layout().addWidget(self.error)
        self.form_card.layout().addWidget(self.success_msg)
        self.form_card.layout().addWidget(self.submit)
        self.form_card.layout().addWidget(self.toggle_btn)

        layout.addStretch(1)
        layout.addWidget(self.brand)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addWidget(self.form_card)
        layout.addStretch(2)

        self.setCentralWidget(root)
        self.update_ui_mode()

    def update_ui_mode(self):
        self.error.hide()
        self.success_msg.hide()

        if self.mode == "login":
            self.title.setText("Sign in")
            self.hint.setText("Use your Supabase account credentials.")
            self.email_label.show()
            self.email.show()
            self.password_label.show()
            self.password.show()
            self.confirm_password_label.hide()
            self.confirm_password.hide()
            self.submit.setText("Log In")
            self.submit.show()
            self.toggle_btn.setText("New here? Create an account")
            self.toggle_btn.show()
            QWidget.setTabOrder(self.email, self.password)
            QWidget.setTabOrder(self.password, self.submit)
            QWidget.setTabOrder(self.submit, self.toggle_btn)
        elif self.mode == "signup":
            self.title.setText("Create Account")
            self.hint.setText("Register a new Supabase user account.")
            self.email_label.show()
            self.email.show()
            self.password_label.show()
            self.password.show()
            self.confirm_password_label.show()
            self.confirm_password.show()
            self.submit.setText("Create Account")
            self.submit.show()
            self.toggle_btn.setText("Already have an account? Log in")
            self.toggle_btn.show()
            QWidget.setTabOrder(self.email, self.password)
            QWidget.setTabOrder(self.password, self.confirm_password)
            QWidget.setTabOrder(self.confirm_password, self.submit)
            QWidget.setTabOrder(self.submit, self.toggle_btn)
        elif self.mode == "confirm_success":
            self.title.setText("Check Your Email")
            self.hint.setText("Account registration submitted successfully.")
            self.email_label.hide()
            self.email.hide()
            self.password_label.hide()
            self.password.hide()
            self.confirm_password_label.hide()
            self.confirm_password.hide()
            self.submit.hide()
            self.success_msg.setText(
                f"We sent a confirmation link to {self.email.text().strip()}.\n\n"
                "Please check your inbox and confirm your account before logging in."
            )
            self.success_msg.show()
            self.toggle_btn.setText("Back to Log In")
            self.toggle_btn.show()
            QWidget.setTabOrder(self.toggle_btn, self.toggle_btn)

    def toggle_mode(self):
        if self.mode == "login":
            self.mode = "signup"
        else:
            self.mode = "login"
        self.update_ui_mode()

    def handle_submit(self):
        if self.mode == "login":
            self.attempt_login()
        elif self.mode == "signup":
            self.attempt_signup()

    def attempt_login(self):
        self.error.hide()
        email = self.email.text().strip()
        password = self.password.text()

        if not email or not password:
            self.error.setText("Please enter both email address and password.")
            self.error.show()
            return

        self.submit.setEnabled(False)
        self.submit.setText("Signing in…")
        QApplication.processEvents()
        try:
            self.auth.sign_in(email, password)
            self.login_succeeded.emit()
        except AuthError as exc:
            self.error.setText(str(exc))
            self.error.show()
        except Exception as exc:
            self.error.setText(f"Login failed: {exc}")
            self.error.show()
        finally:
            self.submit.setEnabled(True)
            self.submit.setText("Log In")

    def attempt_signup(self):
        self.error.hide()
        email = self.email.text().strip()
        password = self.password.text()
        confirm_password = self.confirm_password.text()

        if not email or not password or not confirm_password:
            self.error.setText("All fields are required.")
            self.error.show()
            return

        if "@" not in email or "." not in email:
            self.error.setText("Please enter a valid email address.")
            self.error.show()
            return

        if len(password) < 6:
            self.error.setText("Password must be at least 6 characters long.")
            self.error.show()
            return

        if password != confirm_password:
            self.error.setText("Passwords do not match. Please re-enter.")
            self.error.show()
            return

        self.submit.setEnabled(False)
        self.submit.setText("Creating account…")
        QApplication.processEvents()
        try:
            self.auth.sign_up(email, password)
            self.mode = "confirm_success"
            self.update_ui_mode()
        except AuthError as exc:
            self.error.setText(str(exc))
            self.error.show()
        except Exception as exc:
            self.error.setText(f"Registration failed: {exc}")
            self.error.show()
        finally:
            self.submit.setEnabled(True)
            self.submit.setText("Create Account")


class DropZone(QFrame):
    file_dropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(180)
        layout = QVBoxLayout(self)
        label = QLabel("Drop video file here")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 20px; font-weight: 800;")
        sub = QLabel("MP4, MOV, AVI, MKV")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #8fa1b3;")
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addWidget(sub)
        layout.addStretch(1)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in VIDEO_EXTS:
                self.file_dropped.emit(str(path))
                break


class CalibrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration Parameters")
        self.setMinimumWidth(360)

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.width = QDoubleSpinBox()
        self.width.setRange(0.1, 200.0)
        self.width.setValue(4.0)
        self.width.setSuffix(" m")

        self.length = QDoubleSpinBox()
        self.length.setRange(0.1, 500.0)
        self.length.setValue(8.0)
        self.length.setSuffix(" m")

        self.frame = QSpinBox()
        self.frame.setRange(0, 1000000)

        buttons = QHBoxLayout()
        ok = QPushButton("Start Calibration")
        ok.setObjectName("Primary")
        cancel = QPushButton("Cancel")

        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

        buttons.addWidget(ok)
        buttons.addWidget(cancel)

        layout.addRow("Zone Width", self.width)
        layout.addRow("Zone Length", self.length)
        layout.addRow("Start Frame", self.frame)
        layout.addRow(buttons)

        QWidget.setTabOrder(self.width, self.length)
        QWidget.setTabOrder(self.length, self.frame)
        QWidget.setTabOrder(self.frame, ok)
        QWidget.setTabOrder(ok, cancel)


class HomePage(QWidget):
    start_requested = pyqtSignal(str, int, bool)

    def __init__(self, history_loader, auth: AuthManager | None = None):
        super().__init__()
        self.video_path = None
        self.history_loader = history_loader
        self.auth = auth

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("Video Ingestion")
        title.setObjectName("Title")
        root.addWidget(title)

        top = QHBoxLayout()
        self.drop = DropZone()
        self.drop.file_dropped.connect(self.set_video)
        top.addWidget(self.drop, 3)

        side_layout = QVBoxLayout()
        browse = QPushButton("Browse Video")
        browse.setObjectName("Primary")
        browse.clicked.connect(self.browse)

        self.start = QPushButton("Start Processing")
        self.start.setObjectName("Primary")
        self.start.setEnabled(False)
        self.start.clicked.connect(self.emit_start)

        side_layout.addWidget(browse)
        side_layout.addWidget(self.start)
        side_layout.addStretch(1)
        top.addWidget(card(side_layout), 1)
        root.addLayout(top)

        preview_layout = QGridLayout()
        preview_layout.setHorizontalSpacing(18)
        self.name = QLabel("No video selected")
        self.name.setObjectName("SectionTitle")

        self.meta = QLabel("Drop a video file here or choose Browse to get started.")
        self.meta.setStyleSheet("color: #8fa1b3;")

        self.badge = QLabel("Needs Calibration")
        self.badge.setObjectName("Badge")

        self.calibrate = QPushButton("Calibrate Now")
        self.calibrate.clicked.connect(self.calibrate_now)

        preview_layout.addWidget(self.name, 0, 0, 1, 2)
        preview_layout.addWidget(self.meta, 1, 0, 1, 2)
        preview_layout.addWidget(self.badge, 0, 2)
        preview_layout.addWidget(self.calibrate, 1, 2)
        root.addWidget(card(preview_layout))

        config_layout = QGridLayout()
        model_label = QLabel("YOLOv8 + ByteTrack")
        model_label.setObjectName("DataValue")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 30)
        default_sensitivity = self._default_sensitivity()
        self.slider.setValue(default_sensitivity)
        self.slider_value = QLabel(f"{default_sensitivity} frames")
        self.slider_value.setObjectName("DataValue")
        self.slider.valueChanged.connect(lambda v: self.slider_value.setText(f"{v} frames"))

        self.logs = QCheckBox("Generate detailed log")
        self.logs.setChecked(True)
        self.logs.setToolTip(
            "Always on for now — pipeline JSON/CSV logs are required by the DB importer "
            "and kept for debugging."
        )

        config_layout.addWidget(QLabel("Detection Model"), 0, 0)
        config_layout.addWidget(model_label, 0, 1)
        config_layout.addWidget(QLabel("Sensitivity Threshold"), 1, 0)
        config_layout.addWidget(self.slider, 1, 1)
        config_layout.addWidget(self.slider_value, 1, 2)
        config_layout.addWidget(self.logs, 2, 1)
        root.addWidget(card(config_layout))

        self.recent = QTableWidget(0, 5)
        self.recent.setHorizontalHeaderLabels(["Filename", "Processed", "Vehicles", "Violations", "Peak Speed"])
        self.recent.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent.setMaximumHeight(180)

        root.addWidget(QLabel("Recent Processing History"))
        root.addWidget(self.recent)

        scroll.setWidget(content)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        self.refresh_recent()

    def _default_sensitivity(self) -> int:
        try:
            config = add_pipeline_to_path()
            from app.config import MIN_FRAMES_OVER_LIMIT_TO_FLAG
            return int(MIN_FRAMES_OVER_LIMIT_TO_FLAG)
        except Exception:
            return 5

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select video", "", "Videos (*.mp4 *.mov *.avi *.mkv *.m4v)")
        if path:
            self.set_video(path)

    def set_video(self, path: str):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            meta = read_video_metadata(path)
            size_mb = Path(path).stat().st_size / (1024 * 1024)
            self.video_path = path
            self.name.setText(Path(path).name)
            self.meta.setText(f"{size_mb:.1f} MB | {meta['width']}x{meta['height']} | {meta['fps']:.2f} fps | {meta['duration_sec']:.1f}s")
            self.refresh_calibration()
        except Exception as exc:
            QMessageBox.warning(self, "Video Error", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def refresh_calibration(self):
        calibrated = bool(self.video_path and calibration_path_for(self.video_path).exists())
        self.badge.setText("Calibrated" if calibrated else "Needs Calibration")
        self.badge.setStyleSheet("background: #1f6b45; color: #d9ffe9;" if calibrated else "background: #7a5518; color: #ffe4b8;")
        self.calibrate.setVisible(not calibrated)
        self.start.setEnabled(calibrated)

    def calibrate_now(self):
        if not self.video_path:
            return
        dialog = CalibrationDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            add_pipeline_to_path()
            from app.speed.calibrate_rect import run_calibration
            run_calibration(self.video_path, dialog.width.value(), dialog.length.value(), dialog.frame.value())
            self.refresh_calibration()
        except Exception as exc:
            QMessageBox.warning(self, "Calibration Error", str(exc))

    def emit_start(self):
        if self.video_path:
            self.start_requested.emit(self.video_path, self.slider.value(), self.logs.isChecked())

    def refresh_recent(self):
        rows = self.history_loader(limit=5)
        self.recent.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [row.video_name, str(row.processed_at), row.total_vehicles, row.total_violations, row.peak_speed_kmh]
            for c, value in enumerate(values):
                val_str = "" if value is None else str(value)
                item = QTableWidgetItem(val_str)
                item.setToolTip(val_str)
                self.recent.setItem(r, c, item)


class LivePage(QWidget):
    cancel_requested = pyqtSignal()
    view_results_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._current_image: QImage | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)

        title = QLabel("Camera Feed Analysis")
        title.setObjectName("Title")
        root.addWidget(title)

        body = QHBoxLayout()
        self.video = QLabel("Waiting for processing run")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(480, 320)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        video_card = card(QVBoxLayout())
        video_card.layout().addWidget(self.video)
        body.addWidget(video_card, 3)

        stats_layout = QVBoxLayout()
        self.stat_labels = {}
        for key, label in [("vehicles", "Vehicles Tracked"), ("violations", "Violations"), ("elapsed", "Elapsed time"), ("fps", "FPS")]:
            stats_layout.addWidget(QLabel(label))
            value = QLabel("0")
            value.setObjectName("DataValue")
            self.stat_labels[key] = value
            stats_layout.addWidget(value)

        stats_layout.addStretch(1)

        self.cancel = QPushButton("Cancel Processing")
        self.cancel.setObjectName("Danger")
        self.cancel.clicked.connect(self.cancel_requested.emit)

        self.view_results = QPushButton("View Results")
        self.view_results.setObjectName("Primary")
        self.view_results.hide()
        self.view_results.clicked.connect(lambda: self.view_results_requested.emit(self._complete_video))

        stats_layout.addWidget(self.cancel)
        stats_layout.addWidget(self.view_results)
        body.addWidget(card(stats_layout), 1)

        root.addLayout(body, 1)

        self.progress = QProgressBar()
        root.addWidget(self.progress)
        self._complete_video = ""

    def reset(self):
        self._current_image = None
        self.video.setText("Loading model and video...")
        self.progress.setValue(0)
        self.cancel.show()
        self.view_results.hide()
        for label in self.stat_labels.values():
            label.setText("0")

    def update_frame(self, image: QImage):
        self._current_image = image
        self._render_current_frame()

    def _render_current_frame(self):
        if self._current_image is not None and not self._current_image.isNull():
            scaled_pix = QPixmap.fromImage(self._current_image).scaled(
                self.video.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.video.setPixmap(scaled_pix)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_current_frame()

    def update_stats(self, stats: dict):
        self.stat_labels["vehicles"].setText(str(stats.get("vehicles", 0)))
        self.stat_labels["violations"].setText(str(stats.get("violations", 0)))
        self.stat_labels["elapsed"].setText(f"{stats.get('elapsed_sec', 0):.1f}s")
        self.stat_labels["fps"].setText(f"{stats.get('fps', 0):.1f}")

    def update_progress(self, current: int, total: int):
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(min(current, max(total, 1)))

    def complete(self, result: dict):
        self.cancel.hide()
        self._complete_video = result.get("video_name", "")
        if result.get("cancelled"):
            self.video.setText("Processing cancelled")
            return
        self.video.setText(f"Processing Complete\nVehicles: {result.get('vehicles', 0)}\nViolations: {result.get('violations', 0)}\nTime: {result.get('elapsed_sec', 0):.1f}s")
        self.view_results.show()


class HistoryPage(QWidget):
    def __init__(self, auth: AuthManager | None = None):
        super().__init__()
        self.auth = auth
        self.page = 0
        self.page_size = 25

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        title = QLabel("History")
        title.setObjectName("Title")
        root.addWidget(title)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search filename")

        self.from_date = QDateEdit(QDate.currentDate().addYears(-3))
        self.from_date.setCalendarPopup(True)

        self.to_date = QDateEdit(QDate.currentDate().addDays(1))
        self.to_date.setCalendarPopup(True)

        apply = QPushButton("Apply")
        apply.clicked.connect(self.refresh)

        export_csv = QPushButton("Export CSV")
        export_csv.clicked.connect(self.export_csv)

        export_pdf = QPushButton("Export PDF")
        export_pdf.clicked.connect(self.export_pdf)

        for w in (self.search, self.from_date, self.to_date, apply, export_csv, export_pdf):
            filters.addWidget(w)
        root.addLayout(filters)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Filename", "Date Processed", "Vehicles", "Violations", "Max Speed", "Status"])
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 6):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        header.setMinimumSectionSize(90)

        self.table.itemSelectionChanged.connect(self.refresh_details)

        self.empty_label = QLabel("No processed videos yet\n\nProcess a video from the Home tab to see your processing history here.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setObjectName("EmptyStateSub")
        self.empty_label.setStyleSheet("padding: 40px; background: #111b24; border: 1px dashed #273847; border-radius: 8px;")
        self.empty_label.hide()

        root.addWidget(self.table, 2)
        root.addWidget(self.empty_label)

        pager = QHBoxLayout()
        prev = QPushButton("Previous")
        next_btn = QPushButton("Next")
        prev.clicked.connect(lambda: self.change_page(-1))
        next_btn.clicked.connect(lambda: self.change_page(1))
        pager.addWidget(prev)
        pager.addWidget(next_btn)
        pager.addStretch(1)
        root.addLayout(pager)

        root.addWidget(QLabel("Violation Details"))
        self.details = QTableWidget(0, 4)
        self.details.setHorizontalHeaderLabels(["Track ID", "Peak Speed", "Timestamp", "Confidence"])
        self.details.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.details, 1)

        self.refresh()

    def rows(self, limit=None):
        uid = getattr(self.auth, "user_id", None) if self.auth else None
        if not uid:
            return []
        add_pipeline_to_path()
        from app.database.db import get_session, init_db
        from app.database.models import SessionSummary
        init_db()
        session = get_session()
        try:
            q = session.query(SessionSummary).filter(SessionSummary.user_id == uid)
            term = self.search.text().strip() if hasattr(self, "search") else ""
            if term:
                q = q.filter(SessionSummary.video_name.ilike(f"%{term}%"))
            if hasattr(self, "from_date"):
                q = q.filter(SessionSummary.processed_at >= self.from_date.date().toPyDate())
                q = q.filter(SessionSummary.processed_at <= self.to_date.date().toPyDate())
            q = q.order_by(SessionSummary.processed_at.desc())
            if limit:
                q = q.limit(limit)
            else:
                q = q.offset(self.page * self.page_size).limit(self.page_size)
            return list(q.all())
        finally:
            session.close()

    def refresh(self):
        rows = self.rows()
        if not rows:
            self.table.setRowCount(0)
            self.table.hide()
            self.empty_label.show()
        else:
            self.empty_label.hide()
            self.table.show()
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                values = [row.video_name, str(row.processed_at), row.total_vehicles, row.total_violations, row.peak_speed_kmh, "Complete"]
                for c, value in enumerate(values):
                    val_str = "" if value is None else str(value)
                    item = QTableWidgetItem(val_str)
                    item.setToolTip(val_str)
                    if c == 0:
                        item.setData(Qt.ItemDataRole.UserRole, row.video_name)
                    self.table.setItem(r, c, item)
        self.refresh_details()

    def refresh_details(self):
        uid = getattr(self.auth, "user_id", None) if self.auth else None
        item = self.table.item(self.table.currentRow(), 0) if self.table.currentRow() >= 0 else None
        video_name = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not video_name or not uid:
            self.details.setRowCount(0)
            return
        add_pipeline_to_path()
        from app.database.db import get_session
        from app.database.models import Violation
        session = get_session()
        try:
            rows = session.query(Violation).filter(
                Violation.video_name == video_name,
                Violation.user_id == uid
            ).order_by(Violation.timestamp_sec).all()
            self.details.setRowCount(len(rows))
            for r, row in enumerate(rows):
                values = [row.track_id, row.speed_kmh, f"{row.timestamp_sec:.2f}s", "N/A"]
                for c, value in enumerate(values):
                    val_str = str(value)
                    item = QTableWidgetItem(val_str)
                    item.setToolTip(val_str)
                    self.details.setItem(r, c, item)
        finally:
            session.close()

    def change_page(self, delta):
        self.page = max(0, self.page + delta)
        self.refresh()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "history.csv", "CSV (*.csv)")
        if not path:
            return
        rows = self.rows(limit=100000)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["filename", "date_processed", "vehicle_count", "violation_count", "max_speed", "status"])
            for row in rows:
                writer.writerow([row.video_name, row.processed_at, row.total_vehicles, row.total_violations, row.peak_speed_kmh, "Complete"])

    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "violations.pdf", "PDF (*.pdf)")
        if not path:
            return
        html = ["<h1>Violation Details</h1><table border='1' cellspacing='0' cellpadding='4'><tr><th>Track ID</th><th>Peak Speed</th><th>Timestamp</th><th>Confidence</th></tr>"]
        for r in range(self.details.rowCount()):
            html.append("<tr>" + "".join(f"<td>{self.details.item(r, c).text() if self.details.item(r, c) else ''}</td>" for c in range(4)) + "</tr>")
        html.append("</table>")
        doc = QTextDocument()
        doc.setHtml("".join(html))
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        doc.print(printer)


class MainWindow(QMainWindow):
    logout_requested = pyqtSignal()

    def __init__(self, auth: AuthManager | None = None):
        super().__init__()
        ensure_packaged_runtime_paths()
        self.auth = auth
        self.setWindowTitle("RSZSIS Desktop App")
        self.resize(1280, 820)
        self.setMinimumSize(960, 600)

        self.sync = SyncManager(user_id=getattr(self.auth, "user_id", None), auth=self.auth)
        self.worker = None

        shell = QWidget()
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = self._sidebar()
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.history = HistoryPage(auth=self.auth)
        self.home = HomePage(lambda limit=5: self.history.rows(limit=limit), auth=self.auth)
        self.live = LivePage()

        self.stack.addWidget(self.home)
        self.stack.addWidget(self.live)
        self.stack.addWidget(self.history)
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(shell)

        self.home.start_requested.connect(self.start_processing)
        self.live.cancel_requested.connect(self.cancel_processing)
        self.live.view_results_requested.connect(self.show_history_for)

        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.retry_sync)
        self.sync_timer.start(180000)
        QTimer.singleShot(1000, self.retry_sync)
        self.refresh_sync_badge()

    def _sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(220)

        layout = QVBoxLayout(side)
        layout.setContentsMargins(16, 20, 16, 20)

        brand = QLabel("RSZSIS Desktop")
        brand.setObjectName("Brand")
        layout.addWidget(brand)

        self.nav_buttons = []
        for index, name in enumerate(("Home", "Live Processing", "History")):
            btn = QPushButton(name)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, i=index: self.switch_page(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        self.nav_buttons[0].setChecked(True)
        layout.addStretch(1)

        sys_active = QLabel("System Active")
        sys_active.setStyleSheet("color: #8fa1b3; font-weight: 600; font-size: 12px;")
        layout.addWidget(sys_active)

        self.sync_badge = QLabel("Synced")
        self.sync_badge.setObjectName("SyncBadge")
        layout.addWidget(self.sync_badge)

        if self.auth is not None and self.auth.user_email:
            user_label = QLabel(self.auth.user_email)
            user_label.setObjectName("LoginHint")
            user_label.setWordWrap(True)
            layout.addWidget(user_label)

        logout = QPushButton("Log out")
        logout.clicked.connect(self.logout_requested.emit)
        layout.addWidget(logout)
        return side

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        if index == 0:
            self.home.refresh_recent()
        if index == 2:
            self.history.refresh()

    def start_processing(self, video_path, sensitivity, retain_logs):
        self.switch_page(1)
        self.live.reset()
        owner_uid = getattr(self.auth, "user_id", None)
        self.worker = ProcessingWorker(video_path, sensitivity, retain_logs, owner_user_id=owner_uid, parent=self)
        self.worker.frame_ready.connect(self.live.update_frame)
        self.worker.stats_ready.connect(self.live.update_stats)
        self.worker.progress_ready.connect(self.live.update_progress)
        self.worker.completed.connect(self.processing_complete)
        self.worker.failed.connect(self.processing_failed)
        self.worker.start()

    def cancel_processing(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()

    def processing_complete(self, result):
        self.live.complete(result)
        self.history.refresh()
        self.home.refresh_recent()
        self.refresh_sync_badge()

    def processing_failed(self, message):
        QMessageBox.critical(self, "Processing Failed", message)
        self.live.complete({"cancelled": True})
        self.refresh_sync_badge()

    def show_history_for(self, video_name):
        self.switch_page(2)
        self.history.search.setText(video_name)
        self.history.refresh()

    def retry_sync(self):
        uid = getattr(self.auth, "user_id", None)
        self.sync.retry_pending(user_id=uid)
        self.refresh_sync_badge()

    def refresh_sync_badge(self):
        uid = getattr(self.auth, "user_id", None)
        pending = self.sync.pending_count(user_id=uid)
        self.sync_badge.setText("Synced" if pending == 0 else f"{pending} pending")
        self.sync_badge.setStyleSheet("background: #1f6b45; color: #d9ffe9;" if pending == 0 else "background: #7a5518; color: #ffe4b8;")

    def clear_user_session_data(self):
        self.history.table.setRowCount(0)
        self.history.details.setRowCount(0)
        self.history.page = 0
        self.home.recent.setRowCount(0)
        self.home.video_path = None
        self.home.name.setText("No video selected")
        self.home.meta.setText("Drop a video file here or choose Browse to get started.")
        self.home.badge.setText("Needs Calibration")
        self.home.start.setEnabled(False)
        self.live.reset()


def run_app():
    ensure_packaged_runtime_paths()
    app = QApplication([])
    app.setStyleSheet(STYLE)
    auth = AuthManager()
    state: dict = {"login": None, "main": None}

    def show_login():
        main = state.get("main")
        login = LoginWindow(auth)
        state["login"] = login
        login.login_succeeded.connect(show_shell)
        login.show()
        if main is not None:
            main.close()
            state["main"] = None

    def show_shell():
        login = state.get("login")
        main = MainWindow(auth=auth)
        state["main"] = main
        main.logout_requested.connect(handle_logout)
        main.show()
        if login is not None:
            login.close()
            state["login"] = None

    def handle_logout():
        main = state.get("main")
        if main is not None:
            if main.worker is not None and main.worker.isRunning():
                main.worker.cancel()
                main.worker.wait(2000)
            main.clear_user_session_data()
        auth.sign_out()
        show_login()

    show_login()
    return app.exec()
