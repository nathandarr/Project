"""Promote (or demote) a user to admin from the command line.

Usage:
    python make_admin.py <username>            # grant admin
    python make_admin.py <username> --revoke   # remove admin
"""
import sys

from app import app, db
from models import User


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 1

    username = sys.argv[1]
    revoke = "--revoke" in sys.argv

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user is None:
            print(f"No user named '{username}'.")
            return 1

        user.is_admin = not revoke
        db.session.commit()

        verb = "demoted from admin" if revoke else "promoted to admin"
        print(f"User '{user.username}' has been {verb}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
