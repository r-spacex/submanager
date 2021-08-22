#!/usr/bin/env python3
"""Generate pinned requirements files from the setup.cfg install_requires."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import argparse
import os
import subprocess  # nosec
import sys
from pathlib import (
    Path,
)
from typing import (
    Collection,
    Sequence,
)

# Third party imports
from typing_extensions import (
    Final,
)

# ---- Constants ----

OUTPUT_FILENAME: Final[str] = "requirements{suffix}.txt"
PROJECT_DIR: Final[Path] = Path(__file__).parent.parent

BASE_PIP_COMPILE_INVOCATION: Final[list[str]] = [
    Path(sys.executable).as_posix(),
    "-m",
    "piptools",
    "compile",
    "--upgrade",
    "--strip-extras",
    "--build-isolation",
]
SCRIPT_INVOCATION: Final[list[str]] = [
    "python",
    Path(__file__).relative_to(PROJECT_DIR).as_posix(),
]

# pylint: disable = consider-using-namedtuple-or-dataclass
REQUIREMENT_CONFIGS_ALL: Final[dict[str, tuple[list[str], bool]]] = {
    "DEFAULT": ([], False),
    "lint": (["lint"], False),
    "test": (["test"], False),
    "dev": (["lint", "test"], False),
    "build": (["requirements-build.in"], True),
}


# ---- Main logic ----


def generate_requirements_files(
    req_keys: Collection[str] | None,
    verbose: bool = False,
) -> None:
    """Generate the pinned requirements files with pip-compile."""
    if req_keys:
        known_keys = set(REQUIREMENT_CONFIGS_ALL.keys())
        missing_keys = set(req_keys) - known_keys
        if missing_keys:
            raise KeyError(f"Keys {missing_keys} not found in {known_keys}")
        requirement_configs = {
            req_key: req_value
            for req_key, req_value in REQUIREMENT_CONFIGS_ALL.items()
            if req_key in req_keys
        }
    else:
        requirement_configs = REQUIREMENT_CONFIGS_ALL

    script_invocation_str = " ".join(SCRIPT_INVOCATION)
    env_vars = {**os.environ, "CUSTOM_COMPILE_COMMAND": script_invocation_str}
    for req_name, (extras, allow_unsafe) in requirement_configs.items():
        # Setup args
        if req_name == "DEFAULT":
            output_filename = OUTPUT_FILENAME.format(suffix="")
        else:
            output_filename = OUTPUT_FILENAME.format(suffix=f"-{req_name}")
        if verbose:
            print(f"Generating requirements for {output_filename!r}")

        # Run pip-compile
        extra_args = []
        for extra in extras:
            if extra.endswith(".in"):
                extra_args += [extra]
            else:
                extra_args += ["--extra", extra]
        pip_compile_invocation = [
            *BASE_PIP_COMPILE_INVOCATION,
            "--allow-unsafe" if allow_unsafe else "--no-allow-unsafe",
            "--output-file",
            output_filename,
            *extra_args,
        ]
        pip_compile_result = subprocess.run(  # nosemgrep
            pip_compile_invocation,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            env=env_vars,
            cwd=PROJECT_DIR,
        )
        try:
            pip_compile_result.check_returncode()
        except subprocess.CalledProcessError:
            print("ERROR when running pip-compile:\n", file=sys.stderr)
            print(pip_compile_result.stderr, file=sys.stderr)
            raise

        # Set correct encoding and line endings
        output_path = PROJECT_DIR / output_filename
        with open(output_path, encoding="utf-8") as req_in:
            requirement_contents = req_in.read()
        with open(output_path, "w", encoding="utf-8", newline="\n") as req_out:
            req_out.write(requirement_contents)


def main(sys_argv: Sequence[str] | None = None) -> None:
    """Run the script to generate the requirements files."""
    parser_main = argparse.ArgumentParser(
        description="Generate requirements files with pip-compile",
    )
    parser_main.add_argument(
        "req_keys",
        nargs="*",
        help="The requirement files to generate; all if not passed",
    )

    parsed_args = parser_main.parse_args(sys_argv)
    generate_requirements_files(parsed_args.req_keys, verbose=True)


if __name__ == "__main__":
    main()
