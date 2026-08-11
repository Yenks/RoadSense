"""
Automated UI and Auth verification tests for RSZSIS Desktop App.
Runs headlessly using QT_QPA_PLATFORM=offscreen.
All Supabase Auth calls are strictly mocked.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QHeaderView

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from rszsis_desktop.auth import AuthError, AuthManager
from rszsis_desktop.ui import CalibrationDialog, HistoryPage, HomePage, LivePage, LoginWindow, MainWindow


class TestAuthManagerMocked(unittest.TestCase):

    def setUp(self):
        self.auth = AuthManager()
        self.auth._client = MagicMock()

    def test_sign_up_success(self):
        mock_response = MagicMock()
        self.auth._client.auth.sign_up.return_value = mock_response
        res = self.auth.sign_up("newuser@example.com", "Password123!")
        self.assertEqual(res, mock_response)
        self.auth._client.auth.sign_up.assert_called_once_with({
            "email": "newuser@example.com",
            "password": "Password123!"
        })

    def test_sign_up_short_password(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.sign_up("user@example.com", "123")
        self.assertIn("at least 6 characters", str(ctx.exception))

    def test_sign_up_missing_email(self):
        with self.assertRaises(AuthError) as ctx:
            self.auth.sign_up("", "Password123!")
        self.assertIn("required", str(ctx.exception))

    def test_sign_in_success(self):
        mock_response = MagicMock()
        mock_session = MagicMock()
        mock_session.access_token = "mocked_access_token_123"
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_response.session = mock_session
        mock_response.user = mock_user

        self.auth._client.auth.sign_in_with_password.return_value = mock_response

        res = self.auth.sign_in("test@example.com", "SecretPass123!")
        self.assertTrue(self.auth.is_authenticated)
        self.assertEqual(self.auth.user_email, "test@example.com")


class TestUIWidgetsHeadless(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.auth = AuthManager()
        self.auth._client = MagicMock()

    def test_login_window_mode_switching(self):
        window = LoginWindow(self.auth)
        self.assertEqual(window.mode, "login")
        self.assertEqual(window.title.text(), "Sign in")
        self.assertFalse(window.confirm_password.isVisible())

        # Toggle to signup mode
        window.toggle_mode()
        self.assertEqual(window.mode, "signup")
        self.assertEqual(window.title.text(), "Create Account")
        self.assertFalse(window.confirm_password.isHidden())


        # Toggle back
        window.toggle_mode()
        self.assertEqual(window.mode, "login")

    def test_signup_validation_mismatch(self):
        window = LoginWindow(self.auth)
        window.mode = "signup"
        window.update_ui_mode()
        window.email.setText("test@example.com")
        window.password.setText("Password123!")
        window.confirm_password.setText("Mismatch123!")

        window.attempt_signup()
        self.assertFalse(window.error.isHidden())
        self.assertIn("do not match", window.error.text())

    def test_signup_validation_short_password(self):
        window = LoginWindow(self.auth)
        window.mode = "signup"
        window.update_ui_mode()
        window.email.setText("test@example.com")
        window.password.setText("123")
        window.confirm_password.setText("123")

        window.attempt_signup()
        self.assertFalse(window.error.isHidden())
        self.assertIn("at least 6 characters", window.error.text())

    def test_signup_success_flow(self):
        self.auth._client.auth.sign_up.return_value = MagicMock()
        window = LoginWindow(self.auth)
        window.mode = "signup"
        window.update_ui_mode()
        window.email.setText("validuser@example.com")
        window.password.setText("ValidPassword123!")
        window.confirm_password.setText("ValidPassword123!")

        window.attempt_signup()
        self.assertEqual(window.mode, "confirm_success")
        self.assertEqual(window.title.text(), "Check Your Email")
        self.assertFalse(window.success_msg.isHidden())

    def test_live_page_frame_rescaling(self):
        live = LivePage()
        img = QImage(640, 480, QImage.Format.Format_RGB888)
        img.fill(Qt.GlobalColor.blue)

        live.update_frame(img)
        self.assertIsNotNone(live._current_image)
        self.assertIsNotNone(live.video.pixmap())

        # Simulate window resize
        live.resize(1024, 768)
        live._render_current_frame()
        self.assertIsNotNone(live.video.pixmap())

    @patch.object(HistoryPage, "rows", return_value=[])
    def test_history_page_empty_state_and_table(self, mock_rows):
        history = HistoryPage()
        self.assertFalse(history.empty_label.isHidden())
        self.assertTrue(history.table.isHidden())
        self.assertEqual(history.table.horizontalHeader().sectionResizeMode(0), QHeaderView.ResizeMode.Stretch)


    @patch("rszsis_desktop.ui.SyncManager")
    @patch.object(HistoryPage, "rows", return_value=[])
    def test_main_window_structure(self, mock_rows, mock_sync):
        mock_sync.return_value.pending_count.return_value = 0
        main = MainWindow(self.auth)
        self.assertEqual(main.sidebar.width(), 220)
        self.assertEqual(main.stack.count(), 3)


if __name__ == "__main__":
    unittest.main()

