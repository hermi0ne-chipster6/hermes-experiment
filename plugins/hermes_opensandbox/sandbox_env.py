"""Adapt OpenSandbox's synchronous command stream to Hermes's ProcessHandle."""

from datetime import timedelta
import logging
import os
import shlex
from subprocess import TimeoutExpired
from threading import Event, Lock, Thread

from opensandbox.exceptions import SandboxException
from opensandbox.models.execd import RunCommandOpts
from opensandbox.models.execd_sync import ExecutionHandlersSync
from tools.environments.base import BaseEnvironment, EnvironmentConnectionError

logger = logging.getLogger(__name__)


def remote_error(operation, exc, key):
    status = getattr(exc, "status_code", None)
    prefix = f"HTTP {status}: " if status is not None else ""
    detail = str(exc).replace(key, "<redacted>")
    return EnvironmentConnectionError(f"OpenSandbox could not {operation} ({prefix}{detail})")


class OpenSandboxProcess:
    def __init__(self, commands, command, timeout, api_key):
        self._commands = commands
        self._api_key = api_key
        self._done = Event()
        self._lock = Lock()
        self._cancelled = False
        self._execution_id = None
        self._failure = None
        self.returncode = None
        read_fd, write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, "r", encoding="utf-8", errors="replace")
        writer = os.fdopen(write_fd, "wb")
        needs_separator = False

        def write(text):
            writer.write(text.encode("utf-8"))
            writer.flush()

        def emit(message):
            nonlocal needs_separator
            text = message.text
            if not text:
                return
            # execd v1.1.0 strips nonempty line terminators and provides no
            # flag to distinguish complete lines from flushed fragments.
            # Separate frames in arrival order, including across streams.
            # This keeps mixed output readable without buffering frames or
            # appending a terminator after the last frame.
            if needs_separator:
                text = "\n" + text
            write(text)
            needs_separator = not text.endswith(("\n", "\r"))

        def run():
            try:
                with writer:
                    handlers = ExecutionHandlersSync(
                        on_init=self._started, on_stdout=emit, on_stderr=emit,
                        skip_accumulation=True,
                    )
                    result = commands.run(
                        command, opts=RunCommandOpts(timeout=timedelta(seconds=timeout)),
                        handlers=handlers,
                    )
                    self.returncode = result.exit_code
                    if result.error and result.error.exit_code is None:
                        write(result.error.value.replace(api_key, "<redacted>") + "\n")
                        if self.returncode is None:
                            self.returncode = 1
                    if self.returncode is None:
                        raise EnvironmentConnectionError(
                            "OpenSandbox command stream ended without an exit status."
                        )
            except SandboxException as exc:
                self._failure = remote_error("run command", exc, api_key)
            except Exception as exc:
                self._failure = exc
            finally:
                self._done.set()

        Thread(target=run, daemon=True, name="hermes-opensandbox-command").start()

    def __del__(self):
        # Hermes's normal wait closes stdout. Its interrupt and timeout paths
        # return before that close, and may hand a live handle to the poller.
        if (stream := getattr(self, "stdout", None)) is not None:
            stream.close()

    def _started(self, event):
        with self._lock:
            self._execution_id = event.id
            cancelled = self._cancelled
        if cancelled and event.id:
            self._interrupt(event.id)

    def _interrupt(self, execution_id):
        try:
            self._commands.interrupt(execution_id)
        except SandboxException as exc:
            if getattr(exc, "status_code", None) != 404:
                logger.warning("%s", remote_error("interrupt command", exc, self._api_key))

    def kill(self):
        with self._lock:
            if self._cancelled or self._done.is_set():
                return
            self._cancelled = True
            execution_id = self._execution_id
        if execution_id:
            self._interrupt(execution_id)

    def poll(self):
        if not self._done.is_set():
            return None
        if self._failure:
            raise self._failure
        return self.returncode

    def wait(self, timeout=None):
        if not self._done.wait(timeout):
            raise TimeoutExpired("OpenSandbox command", timeout)
        return self.poll()


class OpenSandboxEnvironment(BaseEnvironment):
    _stdin_mode = "heredoc"

    def __init__(self, sandbox, *, api_key, cwd, timeout):
        super().__init__(cwd=cwd, timeout=timeout)
        self._api_key = api_key
        self._cleanup_lock = Lock()
        self._sandbox = sandbox

    @classmethod
    def initialize(cls, sandbox, *, api_key, cwd, timeout):
        environment = None
        try:
            environment = cls(sandbox, api_key=api_key, cwd=cwd, timeout=timeout)
            environment.init_session()
        except BaseException:
            # Keep teardown with this factory when startup fails, including a
            # partial constructor or an interrupted remote shell bootstrap.
            if environment is not None:
                environment._sandbox = None
            try:
                sandbox.destroy()
            except Exception as exc:
                if getattr(exc, "status_code", None) != 404:
                    logger.warning("%s", remote_error("release uninitialized sandbox", exc, api_key))
            raise
        return environment

    def _run_bash(self, cmd_string, *, login=False, timeout=120, stdin_data=None):
        with self._cleanup_lock:
            if self._sandbox is None:
                raise EnvironmentConnectionError("OpenSandbox session has already been released.")
            commands = self._sandbox.commands
        # The pinned execd accepts shell text. Quote the whole script as one
        # bash argument so the outer execd shell cannot expand it.
        command = shlex.join(["bash", "-lc" if login else "-c", cmd_string])
        return OpenSandboxProcess(commands, command, timeout, self._api_key)

    def cleanup(self):
        with self._cleanup_lock:
            sandbox = self._sandbox
            if sandbox is None:
                return
            try:
                sandbox.kill()
            except SandboxException as exc:
                if getattr(exc, "status_code", None) != 404:
                    raise remote_error("release sandbox", exc, self._api_key) from None
            self._sandbox = None
            sandbox.close()
