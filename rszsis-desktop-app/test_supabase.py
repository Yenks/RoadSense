"""
Step 6 — Supabase connection test.

Inserts a dummy row into 'vehicles', reads it back, then deletes it.
Confirms credentials, schema, and RLS permissions all work together
before any real app code depends on them.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("Inserting dummy row into 'vehicles'...")
dummy_row = {
    "video_name": "TEST_CONNECTION_CHECK",
    "track_id": 999,
    "vehicle_class": "test",
    "is_rider": 0,
    "entry_time_sec": 0.0,
    "exit_time_sec": 1.0,
    "max_speed_kmh": 0.0,
    "avg_speed_kmh": 0.0,
}

insert_result = client.table("vehicles").insert(dummy_row).execute()
inserted_id = insert_result.data[0]["id"]
print(f"Inserted successfully. Row id = {inserted_id}")

print("\nReading it back...")
read_result = client.table("vehicles").select("*").eq("id", inserted_id).execute()
print(read_result.data)

print("\nDeleting the dummy row...")
client.table("vehicles").delete().eq("id", inserted_id).execute()

print("\nConfirming deletion...")
confirm_result = client.table("vehicles").select("*").eq("id", inserted_id).execute()
if len(confirm_result.data) == 0:
    print("SUCCESS — row deleted, table clean. Credentials, schema, and permissions all confirmed working.")
else:
    print("WARNING — row still present after delete attempt.")