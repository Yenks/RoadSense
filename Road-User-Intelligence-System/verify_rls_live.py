import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

uri = os.environ['DATABASE_URI']
engine = create_engine(uri)

with engine.connect() as conn:
    print("=== LIVE POSTGRESQL RLS STATUS ===")
    res = conn.execute(text(
        "SELECT relname, relrowsecurity, relforcerowsecurity "
        "FROM pg_class "
        "WHERE relname IN ('session_summary', 'vehicles', 'violations');"
    )).fetchall()
    for row in res:
        print(f"Table '{row[0]}': RowLevelSecurity={row[1]}, ForceRLS={row[2]}")

    print("\n=== LIVE POSTGRESQL POLICIES ===")
    pol_res = conn.execute(text(
        "SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check "
        "FROM pg_policies "
        "WHERE tablename IN ('session_summary', 'vehicles', 'violations');"
    )).fetchall()
    for p in pol_res:
        print(f"Policy '{p[2]}' on '{p[1]}': cmd={p[5]}, roles={p[4]}, qual={p[6]}, with_check={p[7]}")
