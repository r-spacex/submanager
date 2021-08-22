"""Handle with locking and unlocking the configuration file."""

# Future imports
from __future__ import (
    annotations,
)

# Standard library imports
import os
import time
from pathlib import (
    Path,
)

# Third party imports
from typing_extensions import (
    Final,
)

# Local imports
import submanager.exceptions
import submanager.utils.output
from submanager.constants import (
    CONFIG_PATH_DYNAMIC,
)
from submanager.types import (
    PathLikeStr,
)

LOCK_FILENAME_TEMPLATE: Final[str] = "~{file_name}.lock"

CHECK_INTERVAL_S_DEFAULT: Final[float] = 0.1
TIMEOUT_S_DEFAULT: Final[float] = 60


def generate_lock_file_path(
    config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
) -> Path:
    """Generate the path to the lock file for the given config file."""
    config_path = Path(config_path)
    lock_file_path = config_path.with_name(
        LOCK_FILENAME_TEMPLATE.format(file_name=config_path.name),
    )
    return lock_file_path


def unlock_config(
    config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
) -> bool | None:
    """Unlock the config if its locked by this process."""
    lock_file_path = generate_lock_file_path(config_path)
    if not lock_file_path.exists():
        return None

    with open(lock_file_path, encoding="utf-8") as lock_file:
        pid = lock_file.read()
    if int(pid.strip()) != os.getpid():
        return False

    lock_file_path.unlink()
    return True


def lock_config(config_path: PathLikeStr = CONFIG_PATH_DYNAMIC) -> bool:
    """Lock the config if not locked by another process, optionally waiting."""
    lock_file_path = generate_lock_file_path(config_path)
    current_pid = os.getpid()
    current_pid_str = f"{current_pid}\n"
    if not lock_file_path.exists():
        with open(
            lock_file_path,
            mode="w",
            encoding="utf-8",
            newline="\n",
        ) as lock_file:
            lock_file.write(current_pid_str)
            lock_file.flush()
            os.fsync(lock_file.fileno())
    else:
        return False
    with open(lock_file_path, encoding="utf-8") as lock_file_reread:
        lock_pid = lock_file_reread.read()
    return int(lock_pid.strip()) == os.getpid()


def wait_for_lock(
    config_path: PathLikeStr = CONFIG_PATH_DYNAMIC,
    *,
    raise_error_on_timeout: bool = True,
    timeout_s: float = TIMEOUT_S_DEFAULT,
    check_interval_s: float = CHECK_INTERVAL_S_DEFAULT,
    verbose: bool = False,
) -> bool:
    """Attempt to acquire a lock, waiting until one is available."""
    vprint = submanager.utils.output.VerbosePrinter(enable=verbose)
    config_path = Path(config_path)
    start_time = time.monotonic()
    end_time = start_time + timeout_s

    first_attempt = True
    while time.monotonic() <= end_time:
        acquired_lock = lock_config(config_path)
        if acquired_lock:
            if not first_attempt:
                time_elapsed = time.monotonic() - start_time
                vprint(f"Acquired config lock after {time_elapsed} s")
            return True
        if first_attempt:
            vprint(
                f"File {config_path.as_posix()!r} is locked; "
                f"retrying for {timeout_s} s...",
            )
            first_attempt = False
        time.sleep(check_interval_s)  # nosemgrep

    if not raise_error_on_timeout:
        return False
    raise submanager.exceptions.LockTimeoutError(
        f"Exceeded timeout of {timeout_s} s while attempting to acquire "
        f"a lock on config file at path {config_path.as_posix()!r}",
    )
