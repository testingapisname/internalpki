"""Add the constrained timestamping provisioner to the code-signing CA.

The timestamp provisioner password is streamed to `step` over standard input;
it is not copied into or permanently mounted in the CA container.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
    print("+ " + " ".join(command))
    return subprocess.run(command, check=True, **kwargs)


def main() -> int:
    repository = Path(__file__).resolve().parent.parent
    password_path = (
        repository / "step-ca" / "secrets" / "timestamp-provisioner-password.txt"
    )
    if not password_path.is_file():
        raise SystemExit(
            "Missing timestamp provisioner password; run "
            "python setup/create_secrets.py --group timestamping"
        )

    run(
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--wait",
            "--wait-timeout",
            "60",
            "code-signing-ca",
        ],
        cwd=repository,
    )

    list_command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "code-signing-ca",
        "step",
        "ca",
        "provisioner",
        "list",
        "--ca-url",
        "https://localhost:9001",
        "--root",
        "/codesign/certs/root_ca.crt",
    ]
    listed = run(
        list_command,
        cwd=repository,
        capture_output=True,
        text=True,
    )
    provisioners = json.loads(listed.stdout)
    timestamping_exists = any(
        item.get("name") == "timestamping" for item in provisioners
    )

    common_options = [
        "--ca-url",
        "https://localhost:9001",
        "--root",
        "/codesign/certs/root_ca.crt",
        "--admin-provisioner",
        "codesign-admin",
        "--admin-password-file",
        "/run/secrets/code_signing_ca_password",
        "--x509-template",
        "/codesign/templates/timestamp-authority.tpl",
        "--x509-min-dur",
        "5m",
        "--x509-default-dur",
        "24h",
        "--x509-max-dur",
        "168h",
    ]

    if timestamping_exists:
        update_command = [
            "docker",
            "compose",
            "exec",
            "-T",
            "code-signing-ca",
            "step",
            "ca",
            "provisioner",
            "update",
            "timestamping",
            *common_options,
        ]
        run(update_command, cwd=repository)
        action = "updated"
    else:
        add_command = [
            "docker",
            "compose",
            "exec",
            "-T",
            "code-signing-ca",
            "step",
            "ca",
            "provisioner",
            "add",
            "timestamping",
            "--type",
            "JWK",
            "--create",
            "--password-file",
            "/dev/stdin",
            *common_options,
        ]
        run(add_command, cwd=repository, input=password_path.read_bytes())
        action = "created"
    run(["docker", "compose", "restart", "code-signing-ca"], cwd=repository)
    print(f"Timestamping provisioner {action}; code-signing CA restarted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
