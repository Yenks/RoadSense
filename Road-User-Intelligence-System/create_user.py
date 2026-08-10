"""
One-off script to create dashboard login accounts.
Run this once per person who needs access (you, supervisor, teammates).

Usage:
    python create_user.py
"""

from app.database.db import get_session, init_db
from app.database.models import User


def main():
    init_db()
    session = get_session()

    username = input("Username: ").strip()
    password = input("Password: ").strip()

    if session.query(User).filter(User.username == username).first():
        print(f"User '{username}' already exists.")
        return

    user = User(username=username)
    user.set_password(password)
    session.add(user)
    session.commit()
    session.close()

    print(f"Created user: {username}")


if __name__ == "__main__":
    main()