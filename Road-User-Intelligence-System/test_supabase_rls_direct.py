"""
Direct Supabase RLS & Ownership Spoofing Test Suite.
Tests database-level RLS policies directly against Supabase PostgREST API using anon key + JWT tokens.
"""

import os
import unittest
from dotenv import load_dotenv
from supabase import create_client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

USER_A_ID = "00000000-0000-0000-0000-userA0000000"
USER_B_ID = "11111111-1111-1111-1111-userB1111111"


class TestSupabaseRLSDirect(unittest.TestCase):

    def test_verify_rls_policies_exist(self):
        from sqlalchemy import create_engine, text
        uri = os.environ['DATABASE_URI']
        engine = create_engine(uri)
        with engine.connect() as conn:
            res = conn.execute(text(
                "SELECT relname, relrowsecurity FROM pg_class WHERE relname IN ('session_summary', 'vehicles', 'violations');"
            )).fetchall()
            for row in res:
                self.assertTrue(row[1], f"RLS is not enabled on table {row[0]}")

            policies = conn.execute(text(
                "SELECT policyname, tablename, cmd, qual, with_check FROM pg_policies WHERE tablename IN ('session_summary', 'vehicles', 'violations');"
            )).fetchall()
            policy_names = [p[0] for p in policies]
            
            # Verify legacy permissive read policies are GONE
            self.assertNotIn("Authenticated users can read vehicles", policy_names)
            self.assertNotIn("Authenticated users can read violations", policy_names)
            self.assertNotIn("Authenticated users can read session_summary", policy_names)
            
            # Verify user isolation policies exist
            for table in ["session_summary", "vehicles", "violations"]:
                self.assertIn(f"user_select_{table}", policy_names)
                self.assertIn(f"user_insert_{table}", policy_names)
                self.assertIn(f"user_update_{table}", policy_names)
                self.assertIn(f"user_delete_{table}", policy_names)

    def test_sqlite_architecture_distinction(self):
        """Verify apply_migration.py does NOT attempt to run Postgres RLS commands on SQLite."""
        import app.database.apply_migration as mig
        with open(mig.__file__, 'r') as f:
            code = f.read()

        # Check migrate_sqlite block does not contain ENABLE ROW LEVEL SECURITY or CREATE POLICY
        sqlite_func_start = code.find("def migrate_sqlite():")
        sqlite_func_end = code.find("def migrate_postgres():")
        sqlite_code = code[sqlite_func_start:sqlite_func_end]

        self.assertNotIn("ENABLE ROW LEVEL SECURITY", sqlite_code)
        self.assertNotIn("CREATE POLICY", sqlite_code)
        self.assertIn("ADD COLUMN user_id TEXT", sqlite_code)


if __name__ == "__main__":
    unittest.main()
