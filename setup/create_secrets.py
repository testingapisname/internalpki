"""Interactively create the local secrets required by the PKI lab.

Existing files are never overwritten. Secret values are entered twice and are
written without a trailing newline because Docker mounts the file verbatim.
"""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path


SECRET_GROUPS = {
    "tls": (
        ("ca-password.txt", "TLS CA and initial provisioner password"),
    ),
    "code-signing": (
        ("code-signing-ca-password.txt", "Code-signing CA password"),
        ("publisher-key-password.txt", "Publisher private-key password"),
    ),
    "timestamping": (
        ("timestamp-provisioner-password.txt", "Timestamp provisioner password"),
        ("timestamp-key-password.txt", "Timestamp private-key password"),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create missing Docker secret files for the PKI lab."
    )
    parser.add_argument(
        "--group",
        choices=("all", *SECRET_GROUPS),
        default="all",
        help="secret group to initialize (default: all)",
    )
    return parser.parse_args()


def selected_secrets(group: str) -> list[tuple[str, str]]:
    if group == "all":
        return [item for items in SECRET_GROUPS.values() for item in items]
    return list(SECRET_GROUPS[group])


def write_new_secret(path: Path, value: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, value.encode("utf-8"))
    finally:
        os.close(descriptor)


def main() -> int:
    args = parse_args()
    repository = Path(__file__).resolve().parent.parent
    secret_directory = repository / "step-ca" / "secrets"
    secret_directory.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0

    for filename, label in selected_secrets(args.group):
        path = secret_directory / filename
        if path.exists():
            print(f"SKIP: {path.relative_to(repository)} already exists")
            skipped += 1
            continue

        while True:
            value = getpass.getpass(f"{label}: ")
            confirmation = getpass.getpass("Confirm password: ")
            if not value:
                print("Password cannot be empty; try again.")
            elif value != confirmation:
                print("Passwords did not match; try again.")
            else:
                break

        write_new_secret(path, value)
        print(f"CREATE: {path.relative_to(repository)}")
        created += 1

    print(f"Secret setup complete: created={created}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
