"""
Wrapper around git cmd using subprocess
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass
class GitCmdResult:
    stdout: str
    stderr: str
    retval: int

    @property
    def stderr_and_stdout(self) -> str:
        result = ""
        if self.stdout:
            result += self.stdout

        if not self.stderr:
            return result

        if result:
            result += "\n"

        result += self.stderr
        return result


class GitCMD:
    def __init__(self, cwd: str) -> None:
        self.git_root = cwd
        output = self.git_cmd(["rev-parse", "--show-toplevel"])
        if "not a git repository" in output.stderr:
            raise FileNotFoundError(output.stderr)

        self.git_root = output.stdout.strip()

    def git_cmd(
        self, arguments: list[str], cwd: Optional[str] = None
    ) -> "GitCmdResult":
        if cwd is None:
            context = self.git_root
        else:
            context = cwd

        logger.debug(
            f"Running git cmd: $ git {' '.join(arguments)}; in context {context}"
        )
        process = subprocess.run(
            ["git"] + arguments,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=context,
        )
        stdout = process.stdout.decode()
        stderr = process.stderr.decode()
        logger.debug(
            f"git cmd results: stdout: {stdout}; stderr: {stderr}; "
            f"retval: {process.returncode}"
        )
        return GitCmdResult(
            stdout=stdout.strip(),
            stderr=stderr.strip(),
            retval=process.returncode,
        )

    async def async_git_cmd(
        self, arguments: list[str], cwd: Optional[str] = None
    ) -> "GitCmdResult":
        if cwd is None:
            context = self.git_root
        else:
            context = cwd

        logger.debug(
            f"Running async git cmd: $ git {' '.join(arguments)}; in context {context}"
        )
        async_subprocess = await asyncio.create_subprocess_exec(
            "git",
            *arguments,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=context,
        )
        stdout, stderr = await async_subprocess.communicate()
        logger.debug(
            f"async git cmd results: stdout: {stdout.decode()}; "
            f"stderr: {stderr.decode()}; retval: {async_subprocess.returncode}"
        )
        return GitCmdResult(
            stdout=stdout.decode().strip(),
            stderr=stderr.decode().strip(),
            retval=async_subprocess.returncode,  # type: ignore
        )
