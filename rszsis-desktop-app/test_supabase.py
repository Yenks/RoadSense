"""
Supabase connection test.

Tests connection with SUPABASE_ANON_KEY.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
print("Supabase anon client initialized successfully:", client)