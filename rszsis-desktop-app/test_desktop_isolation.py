"""
Desktop App Data Isolation Unit Test Suite.
"""

import sys
import os
import unittest
from pathlib import Path

# Add paths
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from rszsis_desktop.paths import add_pipeline_to_path
add_pipeline_to_path()

from app.database.db import get_session, init_db
from app.database.models import Vehicle, Violation, SessionSummary
from rszsis_desktop.auth import AuthManager
from rszsis_desktop.sync import SyncManager

USER_A_ID = "00000000-0000-0000-0000-userA0000000"
USER_B_ID = "11111111-1111-1111-1111-userB1111111"


class TestDesktopIsolation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        session = get_session()
        session.query(Vehicle).filter(Vehicle.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        session.query(Violation).filter(Violation.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        session.query(SessionSummary).filter(SessionSummary.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        session.commit()

        # Insert User A session
        session.add(SessionSummary(
            user_id=USER_A_ID,
            video_name="desktop_video_A",
            duration_sec=15.0,
            total_vehicles=3,
            total_violations=1,
        ))
        session.add(Violation(
            user_id=USER_A_ID,
            video_name="desktop_video_A",
            track_id=1,
            vehicle_class="car",
            violation_type="speeding",
            timestamp_sec=2.0,
            speed_kmh=50.0,
            threshold_kmh=30.0,
        ))

        # Insert User B session
        session.add(SessionSummary(
            user_id=USER_B_ID,
            video_name="desktop_video_B",
            duration_sec=20.0,
            total_vehicles=5,
            total_violations=2,
        ))
        session.commit()
        session.close()

    @classmethod
    def tearDownClass(cls):
        session = get_session()
        session.query(Vehicle).filter(Vehicle.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        session.query(Violation).filter(Violation.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        session.query(SessionSummary).filter(SessionSummary.user_id.in_([USER_A_ID, USER_B_ID])).delete(synchronize_session=False)
        session.commit()
        session.close()

    def test_sync_manager_payload_scopes_user_id(self):
        sync = SyncManager(user_id=USER_A_ID)
        payloads = sync._payloads("desktop_video_A", user_id=USER_A_ID)
        self.assertEqual(len(payloads["session_summary"]), 1)
        self.assertEqual(payloads["session_summary"][0]["user_id"], USER_A_ID)
        self.assertEqual(payloads["session_summary"][0]["video_name"], "desktop_video_A")

        # User B sync manager attempting to fetch User A's payload -> MUST return empty
        sync_b = SyncManager(user_id=USER_B_ID)
        payloads_b = sync_b._payloads("desktop_video_A", user_id=USER_B_ID)
        self.assertEqual(len(payloads_b["session_summary"]), 0)

    def test_auth_manager_logout_wipes_user_id(self):
        auth = AuthManager()
        auth.user_id = USER_A_ID
        auth.user_email = "user_a@example.com"
        auth.sign_out()

        self.assertIsNone(auth.user_id)
        self.assertIsNone(auth.user_email)
        self.assertIsNone(auth.session)


if __name__ == "__main__":
    unittest.main()
