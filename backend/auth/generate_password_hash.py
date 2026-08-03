"""
CLI helper: generate a bcrypt hash for ADMIN_PASSWORD_HASH in .env.

Usage:
  python -m backend.auth.generate_password_hash "your-chosen-password"
"""

from __future__ import annotations

import sys

import bcrypt


def hash_password(plain: str) -> str:
    # bcrypt only uses the first 72 bytes
    raw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(
            'Usage: python -m backend.auth.generate_password_hash "your-chosen-password"',
            file=sys.stderr,
        )
        sys.exit(1)
    print(hash_password(sys.argv[1]))


if __name__ == "__main__":
    main()
