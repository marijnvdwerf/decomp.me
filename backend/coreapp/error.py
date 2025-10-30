import logging
from sqlite3 import IntegrityError
from subprocess import CalledProcessError
from typing import Any, ClassVar, Optional

from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: Any) -> Optional[Response]:
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    if isinstance(exc, SubprocessError):
        detail = exc.render_message()
        payload: dict[str, Any] = {
            "code": exc.SUBPROCESS_NAME,
            "detail": detail or exc.msg,
        }
        if exc.command:
            payload["command"] = exc.command
        if exc.stdout:
            payload["stdout"] = exc.stdout
        if exc.stderr and exc.stderr != exc.stdout:
            payload["stderr"] = exc.stderr

        response = Response(
            data=payload,
            status=HTTP_400_BAD_REQUEST,
        )

        log_lines = [
            f"Subprocess error in {exc.SUBPROCESS_NAME}",
        ]
        if exc.command:
            log_lines.append(f"Command: {exc.command}")
        if detail:
            log_lines.append("Message:")
            log_lines.append(detail)
        else:
            log_lines.append(f"Message: {exc.msg}")
        if exc.stdout:
            log_lines.append("Stdout:")
            log_lines.append(exc.stdout)
        if exc.stderr and exc.stderr != exc.stdout:
            log_lines.append("Stderr:")
            log_lines.append(exc.stderr)
        logger.error("\n".join(log_lines))
    elif isinstance(exc, AssertionError) or isinstance(exc, IntegrityError):
        response = Response(
            data={
                "detail": str(exc),
            },
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if response is not None and isinstance(response.data, dict):
        response.data["kind"] = exc.__class__.__name__

    return response


class SubprocessError(Exception):
    SUBPROCESS_NAME: ClassVar[str] = "Subprocess"
    msg: str
    stdout: str
    stderr: str
    command: Optional[str]

    def __init__(
        self,
        message: str,
        stdout: str = "",
        stderr: str = "",
        command: Optional[str] = None,
    ):
        base_message = message.strip()
        self.msg = (
            f"{self.SUBPROCESS_NAME} error: {base_message}"
            if base_message
            else f"{self.SUBPROCESS_NAME} error"
        )

        super().__init__(self.msg)
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        self.command = command

    def render_message(self) -> str:
        text = (self.stdout or "").strip()
        if text:
            return text
        text = (self.stderr or "").strip()
        if text:
            return text
        return self.msg

    @classmethod
    def from_process_error(cls, ex: CalledProcessError) -> "SubprocessError":
        stdout = (ex.stdout or "").strip()
        stderr = (ex.stderr or "").strip()
        command: Optional[str]
        if isinstance(ex.cmd, (list, tuple)):
            command = " ".join(str(part) for part in ex.cmd)
        else:
            command = str(ex.cmd) if ex.cmd is not None else None

        message = stdout or stderr
        if not message:
            if command:
                message = f"{command} returned {ex.returncode}"
            else:
                message = f"Process returned {ex.returncode}"

        error = cls(
            message,
            stdout=stdout,
            stderr=stderr,
            command=command,
        )
        return error


class DiffError(SubprocessError):
    SUBPROCESS_NAME: ClassVar[str] = "Diff"


class ObjdumpError(SubprocessError):
    SUBPROCESS_NAME: ClassVar[str] = "objdump"


class NmError(SubprocessError):
    SUBPROCESS_NAME: ClassVar[str] = "nm"


class CompilationError(SubprocessError):
    SUBPROCESS_NAME: ClassVar[str] = "Compiler"


class SandboxError(SubprocessError):
    SUBPROCESS_NAME: ClassVar[str] = "Sandbox"


class AssemblyError(SubprocessError):
    SUBPROCESS_NAME: ClassVar[str] = "Compiler"

    @classmethod
    def from_process_error(cls, ex: CalledProcessError) -> "SubprocessError":
        error = super().from_process_error(ex)

        error_lines = []
        for line in (ex.stdout or "").splitlines():
            if "asm.s:" in line:
                error_lines.append(line[line.find("asm.s:") + len("asm.s:") :].strip())
            else:
                error_lines.append(line)
        error.msg = "\n".join(error_lines)
        if not error.msg:
            error.msg = error.render_message()

        return error
