# app/core/logger.py
import os
import sys
import threading
from datetime import datetime as dt, timezone
from typing import TextIO

_COLORS = {
    "black": 30, "red": 31, "green": 32, "yellow": 33,
    "blue": 34, "magenta": 35, "cyan": 36, "white": 37,
}
_BOLD = "1"
_RESET = "\033[0m"


def colorize(text: str, fg: str | None = None, bold: bool = False) -> str:
    """Wrap text in ANSI color codes (replacement for django.utils.termcolors.colorize)."""
    codes = []
    if fg:
        codes.append(str(_COLORS[fg]))
    if bold:
        codes.append(_BOLD)
    if not codes:
        return text
    return f"\033[{';'.join(codes)}m{text}{_RESET}"


def _supports_color(stream: TextIO) -> bool:
    """Color only when writing to a real terminal, unless overridden by env vars."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


class FastAPILogger:
    """
    Logger that mimics Django management command output:

        logger.info("...")
        logger.success("...")
        logger.warning("...")
        logger.error("...")

    With terminal color formatting.

    Note: Only supports f-strings, not '%s' or '%d' like the standard logging module.
    """

    def __init__(
        self,
        stream: TextIO | None = None,
        time_format: str = "%Y-%m-%d %H:%M:%S",
        use_color: bool | None = None,  # None = auto-detect
    ):
        self.stdout = stream or sys.stdout
        self.stderr = sys.stderr
        self.time_format = time_format
        self._use_color = use_color
        self._lock = threading.Lock()

    # ----------------------------
    # Formatting helpers
    # ----------------------------
    def _timestamp(self) -> str:
        return dt.now(timezone.utc).strftime(self.time_format)

    def _color_enabled(self, stream: TextIO) -> bool:
        if self._use_color is not None:
            return self._use_color
        return _supports_color(stream)

    def _write(self, message: str, color: str | None = None, stderr: bool = False) -> None:
        stream = self.stderr if stderr else self.stdout

        line = f"[{self._timestamp()}] {message}"

        if color and self._color_enabled(stream):
            line = colorize(line, fg=color, bold=(color == "green"))

        # Like Django's OutputWrapper: always end with a newline.
        if not line.endswith("\n"):
            line += "\n"

        # Lock so lines from different threads never interleave.
        with self._lock:
            stream.write(line)
            stream.flush()

    # ----------------------------
    # Public logging methods
    # ----------------------------
    def info(self, message: str) -> None:
        self._write(f"[INFO] {message}", color="cyan")

    def write(self, message: str) -> None:
        self._write(f"[INFO] {message}", color="white")

    def success(self, message: str) -> None:
        self._write(f"[SUCCESS] {message}", color="green")

    def warning(self, message: str) -> None:
        self._write(f"[WARNING] {message}", color="yellow")

    def error(self, message: str) -> None:
        self._write(f"[ERROR] {message}", color="red", stderr=True)

    def exception(self, message: str) -> None:
        """Like error(), but also prints the traceback when called inside an except block."""
        if sys.exc_info()[0] is not None:
            import traceback
            message = f"{message}\n{traceback.format_exc().rstrip()}"
        self._write(f"[ERROR] {message}", color="red", stderr=True)

    def debug(self, message: str) -> None:
        self._write(f"[DEBUG] {message}", color="magenta", stderr=True)


logger = FastAPILogger()