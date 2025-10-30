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
        response = Response(
            data={
                "code": exc.SUBPROCESS_NAME,
                "detail": detail,
                **({"stdout": exc.stdout} if exc.stdout else {}),
                **({"stderr": exc.stderr} if exc.stderr else {}),
            },
            status=HTTP_400_BAD_REQUEST,
        )
        logger.error(
            "Subprocess error in %s: %s",
            exc.SUBPROCESS_NAME,
            detail or exc.msg,
            extra={
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            },
        )
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

    def __init__(self, message: str, stdout: str = "", stderr: str = ""):
        self.msg = f"{self.SUBPROCESS_NAME} error: {message}".strip()

        super().__init__(self.msg)
        self.stdout = stdout or ""
        self.stderr = stderr or ""

    def render_message(self) -> str:
        text = (self.stdout or "").strip()
        if text:
            return text
        text = (self.stderr or "").strip()
        if text:
            return text
        return self.msg

    @staticmethod
    def from_process_error(ex: CalledProcessError) -> "SubprocessError":
        stdout = (ex.stdout or "").strip()
        stderr = (ex.stderr or "").strip()
        message = stdout or stderr or f"{ex.cmd[0]} returned {ex.returncode}"
        error = SubprocessError(
            message,
            stdout=stdout,
            stderr=stderr,
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

    @staticmethod
    def from_process_error(ex: CalledProcessError) -> "SubprocessError":
        error = super(AssemblyError, AssemblyError).from_process_error(ex)

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
