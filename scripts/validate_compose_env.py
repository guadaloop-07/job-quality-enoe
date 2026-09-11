"""Validate the non-secret shape of the local Compose environment file."""

from __future__ import annotations

import argparse
from pathlib import Path

REQUIRED = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
TEMPLATE_PASSWORD = "change-me-before-starting"


def read_env(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE entries without printing their values."""
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number} must use KEY=VALUE syntax")
        key, value = line.split("=", maxsplit=1)
        values[key.strip()] = value.strip()
    return values


def validate(path: Path) -> list[str]:
    """Return actionable errors while keeping all configuration values private."""
    if not path.is_file():
        return [f"Missing {path.name}. Copy .env.example to {path.name} and set its values."]

    try:
        values = read_env(path)
    except ValueError as error:
        return [str(error)]

    errors = [f"Missing required setting: {key}" for key in REQUIRED if not values.get(key)]
    if values.get("POSTGRES_PASSWORD") == TEMPLATE_PASSWORD:
        errors.append("POSTGRES_PASSWORD still uses the template value; choose a local credential.")

    port = values.get("POSTGRES_PORT", "5435")
    try:
        port_number = int(port)
    except ValueError:
        errors.append("POSTGRES_PORT must be an integer between 1 and 65535.")
    else:
        if not 1 <= port_number <= 65535:
            errors.append("POSTGRES_PORT must be an integer between 1 and 65535.")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    errors = validate(args.env_file)
    if errors:
        for error in errors:
            print(f"Configuration error: {error}")
        raise SystemExit(2)
    print(f"Local Compose configuration is valid: {args.env_file}")


if __name__ == "__main__":
    main()
