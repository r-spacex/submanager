#!/usr/bin/env python3
"""Generate pinned requirements files from the setup.cfg install_requires."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import os
import subprocess  # nosec
import sys
from pathlib import (
    Path,
)

# Third party imports
from typing_extensions import (
    Final,
)

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

REQUIREMENT_CONFIGS: Final[list[tuple[str, list[str], bool]]] = [
    ("", [], False),
    ("lint", ["lint"], False),
    ("release", ["release"], True),
    ("test", ["test"], False),
    ("dev", ["lint", "test"], False),
]


def main() -> None:
    """Generate the pinned requirements files with pip-compile."""
    script_invocation_str = " ".join(SCRIPT_INVOCATION)
    env_vars = {**os.environ, "CUSTOM_COMPILE_COMMAND": script_invocation_str}
    for req_name, extras, allow_unsafe in REQUIREMENT_CONFIGS:
        # Setup args
        if req_name:
            output_filename = OUTPUT_FILENAME.format(suffix=f"-{req_name}")
        else:
            output_filename = OUTPUT_FILENAME.format(suffix="")
        print(f"Generating requirements for {output_filename!r}")

        # Run pip-compile
        extra_args = []
        for extra in extras:
            extra_args += ["--extra", extra]
        pip_compile_invocation = [
            *BASE_PIP_COMPILE_INVOCATION,
            "--allow-unsafe" if allow_unsafe else "--no-allow-unsafe",
            "--output-file",
            output_filename,
            *extra_args,
        ]
        pip_compile_result = subprocess.run(
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


if __name__ == "__main__":
    main()
