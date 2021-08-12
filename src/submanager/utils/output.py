"""Utility functions and classes for handling and printing output."""

# Future imports
from __future__ import (
    annotations,
)


def format_error(error: BaseException) -> str:
    """Format an error as a human-readible string."""
    return f"{type(error).__name__}: {error}"


def print_error(error: BaseException) -> None:
    """Print the error in a human-readible format for end users."""
    print(format_error(error))


class VerbosePrinter:
    """Simple wrapper that only prints if verbose is set."""

    def __init__(self, enable: bool = True) -> None:
        self.enable = enable

    def __call__(self, *text: str) -> None:
        """If verbose is set, print the text."""
        if self.enable:
            print(*text)


class FancyPrinter(VerbosePrinter):
    """Simple print wrapper with a few extra features."""

    def __init__(
        self,
        enable: bool = True,
        *,
        char: str = "#",
        step: int = 6,
        level: int | None = None,
        sep: str = " ",
        before: str = "",
        after: str = "",
    ) -> None:
        super().__init__(enable=enable)
        self.char = char
        self.step = step
        self.level = level
        self.sep = sep
        self.before = before
        self.after = after

    def wrap_text(self, *text: str, level: int | None) -> str:
        """Wrap the text in the configured char, up to the specified level."""
        text_joined = self.sep.join(text)
        if level and level > 0:
            wrapping = self.char * (level * self.step)
            text_joined = f"{wrapping} {text_joined} {wrapping}"
        text_joined = f"{self.before}{text_joined}{self.after}"
        return text_joined

    def __call__(self, *text: str, level: int | None = None) -> None:
        """Wrap the text at a certain level given the defaults."""
        print(self.wrap_text(*text, level=level))
