from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

from .paths import ENV_PATH

log = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when email/password sign-in fails."""


class AuthManager:
    """Shared login gate — session is held for the app runtime only.

    Uses a Supabase client initialized with SUPABASE_ANON_KEY only.
    Sync writes (Task 5) use a separate service_role client in SyncManager.
    """

    def __init__(self):
        self._client = None
        self.session = None
        self.user_email: str | None = None

    def _create_client(self):
        load_dotenv(ENV_PATH)
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        if not url:
            raise RuntimeError("SUPABASE_URL is required in .env")
        if not key:
            raise RuntimeError(
                "SUPABASE_ANON_KEY is required in .env for authentication. "
                "Do not use SUPABASE_SERVICE_KEY for login."
            )
        from supabase import create_client
        return create_client(url, key)

    def connect(self):
        if self._client is None:
            self._client = self._create_client()
        return self._client

    @property
    def access_token(self) -> str | None:
        if self.session is None:
            return None
        return getattr(self.session, "access_token", None)

    @property
    def is_authenticated(self) -> bool:
        return self.session is not None and bool(self.access_token)

    def sign_in(self, email: str, password: str) -> Any:
        email = (email or "").strip()
        if not email or not password:
            raise AuthError("Email and password are required.")
        try:
            # supabase-py takes a credentials dict, not positional email/password.
            response = self.connect().auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        except AuthError:
            raise
        except Exception as exc:
            message = str(exc).strip() or "Login failed."
            raise AuthError(message) from exc

        session = getattr(response, "session", None)
        if session is None or not getattr(session, "access_token", None):
            raise AuthError("Login failed: no session returned.")

        self.session = session
        user = getattr(response, "user", None) or getattr(session, "user", None)
        self.user_email = getattr(user, "email", None) or email
        return response

    def sign_out(self) -> None:
        try:
            if self._client is not None:
                self._client.auth.sign_out()
        except Exception:
            log.exception("Supabase sign_out failed; clearing local session anyway")
        finally:
            self.session = None
            self.user_email = None
            # Drop the client so the next login recreates an anon-key client cleanly.
            self._client = None
