"""
Automated security test suite for P0 Data Isolation — CivicShield & RSZSIS Desktop.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database.db import get_session, init_db
from app.database.models import Vehicle, Violation, SessionSummary
from app.auth import SupabaseUser

USER_A_ID = "00000000-0000-0000-0000-userA0000000"
USER_B_ID = "11111111-1111-1111-1111-userB1111111"

USER_A_EMAIL = "user_a@example.com"
USER_B_EMAIL = "user_b@example.com"


class TestDataIsolation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        db = get_session()
        # Clean up test rows first
        db.query(Vehicle).filter(Vehicle.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        db.query(Violation).filter(Violation.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        db.query(SessionSummary).filter(SessionSummary.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        db.commit()

        # Insert User A test data
        db.add(SessionSummary(
            user_id=USER_A_ID,
            video_name="user_a_video_001",
            duration_sec=30.0,
            total_vehicles=5,
            avg_speed_kmh=42.0,
            peak_speed_kmh=65.0,
            total_violations=2,
        ))
        db.add(Vehicle(
            user_id=USER_A_ID,
            video_name="user_a_video_001",
            track_id=1,
            vehicle_class="car",
            is_rider=0,
            entry_time_sec=1.0,
            exit_time_sec=10.0,
            max_speed_kmh=65.0,
            avg_speed_kmh=42.0,
        ))
        db.add(Violation(
            user_id=USER_A_ID,
            video_name="user_a_video_001",
            track_id=1,
            vehicle_class="car",
            violation_type="speeding",
            timestamp_sec=5.0,
            speed_kmh=65.0,
            threshold_kmh=30.0,
            snapshot_path="user_a_snap_1.jpg",
        ))

        # Insert User B test data
        db.add(SessionSummary(
            user_id=USER_B_ID,
            video_name="user_b_video_999",
            duration_sec=20.0,
            total_vehicles=2,
            avg_speed_kmh=25.0,
            peak_speed_kmh=35.0,
            total_violations=1,
        ))
        db.add(Violation(
            user_id=USER_B_ID,
            video_name="user_b_video_999",
            track_id=10,
            vehicle_class="truck",
            violation_type="speeding",
            timestamp_sec=8.0,
            speed_kmh=35.0,
            threshold_kmh=30.0,
            snapshot_path="user_b_snap_9.jpg",
        ))

        db.commit()
        db.close()

    @classmethod
    def tearDownClass(cls):
        db = get_session()
        db.query(Vehicle).filter(Vehicle.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        db.query(Violation).filter(Violation.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        db.query(SessionSummary).filter(SessionSummary.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        db.commit()
        db.close()

    def _mock_get_user(self, token):
        mock_user = MagicMock()
        if token == "token_A":
            mock_user.id = USER_A_ID
            mock_user.email = USER_A_EMAIL
        elif token == "token_B":
            mock_user.id = USER_B_ID
            mock_user.email = USER_B_EMAIL
        else:
            return None
        res = MagicMock()
        res.user = mock_user
        return res

    def test_user_a_sees_only_user_a_data(self):
        with patch('app.auth.supabase_client.auth.get_user', side_effect=self._mock_get_user):
            from app.main import create_app
            app = create_app()
            app.config['TESTING'] = True
            client = app.test_client()

            with client.session_transaction() as sess:
                sess['_user_id'] = "token_A"

            # User A dashboard
            res = client.get("/dashboard")
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("user_a_video_001", html)
            self.assertNotIn("user_b_video_999", html)

            # User A video detail
            res = client.get("/video/user_a_video_001")
            self.assertEqual(res.status_code, 200)

            # User A violations
            res = client.get("/violations")
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("user_a_video_001", html)
            self.assertNotIn("user_b_video_999", html)

    def test_user_b_cannot_access_user_a_video_detail(self):
        with patch('app.auth.supabase_client.auth.get_user', side_effect=self._mock_get_user):
            from app.main import create_app
            app = create_app()
            app.config['TESTING'] = True
            client = app.test_client()

            with client.session_transaction() as sess:
                sess['_user_id'] = "token_B"

            # User B attempts to access User A's video details -> MUST return 404
            res = client.get("/video/user_a_video_001")
            self.assertEqual(res.status_code, 404)

    def test_user_b_cannot_access_user_a_snapshot(self):
        with patch('app.auth.supabase_client.auth.get_user', side_effect=self._mock_get_user):
            from app.main import create_app
            app = create_app()
            app.config['TESTING'] = True
            client = app.test_client()

            with client.session_transaction() as sess:
                sess['_user_id'] = "token_B"

            # User B attempts to access User A's snapshot -> MUST return 404
            res = client.get("/snapshot/user_a_video_001/user_a_snap_1.jpg")
            self.assertEqual(res.status_code, 404)

    def test_path_traversal_snapshot_blocked(self):
        with patch('app.auth.supabase_client.auth.get_user', side_effect=self._mock_get_user):
            from app.main import create_app
            app = create_app()
            app.config['TESTING'] = True
            client = app.test_client()

            with client.session_transaction() as sess:
                sess['_user_id'] = "token_A"

            # Path traversal attempts
            traversals = [
                "/snapshot/../config.py/user_a_snap_1.jpg",
                "/snapshot/user_a_video_001/../../config.py",
                "/snapshot/..%2fuser_a_video_001/user_a_snap_1.jpg",
                "/snapshot/user_a_video_001/..%2f..%2fconfig.py",
            ]
            for url in traversals:
                res = client.get(url)
                # Must return 404 or 400 (never 200 or raw file leak)
                self.assertIn(res.status_code, [404, 400], f"Path traversal attempt {url} returned {res.status_code}")

    def test_user_b_export_does_not_contain_user_a_violations(self):
        with patch('app.auth.supabase_client.auth.get_user', side_effect=self._mock_get_user):
            from app.main import create_app
            app = create_app()
            app.config['TESTING'] = True
            client = app.test_client()

            with client.session_transaction() as sess:
                sess['_user_id'] = "token_B"

            res = client.get("/export/violations")
            self.assertEqual(res.status_code, 200)
            csv_text = res.get_data(as_text=True)
            self.assertIn("user_b_video_999", csv_text)
            self.assertNotIn("user_a_video_001", csv_text)

    def test_unauthenticated_access_blocked(self):
        from app.main import create_app
        app = create_app()
        app.config['TESTING'] = True
        client = app.test_client()

        for endpoint in ["/dashboard", "/videos", "/video/user_a_video_001", "/violations", "/export/violations"]:
            res = client.get(endpoint)
            self.assertEqual(res.status_code, 302, f"Endpoint {endpoint} allowed unauthenticated access!")
            self.assertIn("/login", res.headers["Location"])


if __name__ == "__main__":
    unittest.main()
