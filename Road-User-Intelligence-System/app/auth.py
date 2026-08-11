"""
Supabase Auth adapter for Flask-Login — Week 9 (v3).

The dashboard no longer manages its own local user table/password hashes.
Login is delegated entirely to Supabase Auth — the same accounts used by
the desktop app. Flask-Login still manages the Flask-side session, but the
"user" object it loads is a lightweight wrapper around the Supabase access
token, re-verified against Supabase on every page load.
"""

import os
from flask_login import UserMixin
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


class SupabaseUser(UserMixin):
    """get_id() returns the Supabase access token — Flask-Login stores
    this in the session cookie and passes it back to the user_loader on
    every request to re-verify."""

    def __init__(self, access_token: str, email: str, user_id: str):
        self.access_token = access_token
        self.email = email
        self.user_id = user_id

    def get_id(self):
        return self.access_token


def authenticate(email: str, password: str) -> SupabaseUser:
    """Raises an exception on bad credentials — caller should catch it."""
    result = supabase_client.auth.sign_in_with_password({
        "email": email,
        "password": password,
    })
    return SupabaseUser(
        access_token=result.session.access_token,
        email=result.user.email,
        user_id=result.user.id,
    )


def load_user_from_token(access_token: str):
    """Used by Flask-Login's user_loader. Returns None (forcing re-login)
    if the token is invalid or expired."""
    try:
        response = supabase_client.auth.get_user(access_token)
        if response and response.user:
            return SupabaseUser(
                access_token=access_token,
                email=response.user.email,
                user_id=response.user.id,
            )
    except Exception:
        pass
    return None


def sign_up_user(email: str, password: str):
    """Delegates user registration to Supabase Auth.
    Returns the Supabase response object, or raises an exception on failure."""
    return supabase_client.auth.sign_up({
        "email": email,
        "password": password,
    })