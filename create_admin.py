"""
create_admin.py - Create an admin login, or get back into one, from the command line.

No verification email is needed, so this works before SMTP is set up. If the email already
has an account, it becomes an admin, is reactivated and gets the new password.

    python3 create_admin.py --email you@example.com --name "Your Name"

The password is asked for (hidden), or read from ADMIN_PASSWORD if that is set.
"""
import argparse
import getpass
import os
import sys

import auth
import database as db


def main():
    parser = argparse.ArgumentParser(description="Create or reset an admin account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="")
    args = parser.parse_args()

    db.init_db()
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Confirm password: "):
            sys.exit("The two passwords don't match.")
    existed = db.get_account_by_email(args.email) is not None
    account, err = auth.set_up_admin(args.name, args.email, password)
    if err:
        sys.exit(err)
    print(f"{'Updated' if existed else 'Created'} admin {account['name']} <{account['email']}>. Log in with that email and password.")


if __name__ == "__main__":
    main()
