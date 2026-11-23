"""Provider fixtures using pinned Hermes core, with a synthetic OpenSandbox client."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from agent import terminal_env_registry
from agent.terminal_env_provider import TerminalEnvironmentProvider
from opensandbox.config.connection_sync import ConnectionConfigSync
from opensandbox.exceptions import SandboxApiException, SandboxException
from opensandbox.models.sandboxes import SandboxEndpoint
from opensandbox.sync.adapters.command_adapter import CommandsAdapterSync
from opensandbox.sync.adapters.sandboxes_adapter import SandboxesAdapterSync
from tools.environments.base import EnvironmentConnectionError
from tools.terminal_tool_backends import _create_environment


WRITE_MARKER = """printf '%s' "B's synthetic marker" > write_fixture_marker"""


def load_plugin():
    path = Path(__file__).resolve().parents[1] / "__init__.py"
    if not path.exists():
        raise AssertionError("OpenSandbox plugin package is missing")
    spec = importlib.util.spec_from_file_location(
        "hermes_opensandbox_fixture", path, submodule_search_locations=[str(path.parent)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SyntheticSandbox:
    """Scripted fixture with a file namespace separate from the controller."""

    def __init__(self):
        self.files = {}
        self.kills = 0
        self.closed = False
        self.interrupted = threading.Event()
        self.commands = self

    def run(self, command, *, opts, handlers):
        if not isinstance(command, str):
            raise SandboxApiException("fixture requires a string command", status_code=400)
        argv = shlex.split(command)
        assert len(argv) == 3 and argv[:2] in (["bash", "-lc"], ["bash", "-c"])
        assert opts.timeout.total_seconds() > 0
        script = argv[-1]
        handlers.on_init(SimpleNamespace(id="synthetic-command"))
        if "write_fixture_marker" in script:
            # BaseEnvironment quotes its script again for the inner eval.
            assert WRITE_MARKER.replace("'", "'\\''") in script
            self.files["marker.txt"] = "B's synthetic marker"
        elif "read_fixture_marker" in script:
            handlers.on_stdout(SimpleNamespace(text=self.files["marker.txt"], is_error=False))
        elif "fixture_nonzero" in script:
            return SimpleNamespace(exit_code=7, error=None, complete=True)
        elif "fixture_failed_to_start" in script:
            return SimpleNamespace(
                exit_code=None, error=SimpleNamespace(exit_code=None, value="fixture failed to start")
            )
        elif "fixture_transport_error" in script:
            raise SandboxException("private execution fixture stopped responding")
        elif "fixture_cancel" in script:
            if not self.interrupted.wait(8):
                raise AssertionError("remote interrupt was not dispatched")
        elif "hermes-snap-" not in script:
            raise AssertionError("fixture received an unexpected command")
        return SimpleNamespace(exit_code=0, error=None, complete=True)

    def interrupt(self, execution_id):
        assert execution_id == "synthetic-command"
        self.interrupted.set()

    def kill(self):
        self.kills += 1

    def close(self):
        self.closed = True

    def destroy(self):
        try:
            self.kill()
        finally:
            self.close()


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        self.plugin.register(
            SimpleNamespace(register_terminal_environment_provider=terminal_env_registry.register_provider)
        )
        self.provider = terminal_env_registry.get_provider("opensandbox")
        self.assertIsNotNone(self.provider)
        self.addCleanup(terminal_env_registry.restore_registration, "opensandbox", self.provider, None)
        self.env_patch = patch.dict(
            os.environ, {"OPEN_SANDBOX_DOMAIN": "127.0.0.1:18080", "OPEN_SANDBOX_API_KEY": "fixture-only"}
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_registers_native_backend(self):
        self.assertIsInstance(self.provider, TerminalEnvironmentProvider)
        self.assertEqual(self.provider.name, "opensandbox")
        self.assertTrue(self.provider.is_remote)
        self.assertFalse(self.provider.skip_container_guards)
        self.assertFalse(self.provider.supports_streams)
        self.assertIn("OPEN_SANDBOX_API_KEY", self.provider.strip_env_keys)

    def test_remote_file_lifecycle_preserves_exit_status_and_releases_handle(self):
        box = SyntheticSandbox()
        with patch("opensandbox.sync.SandboxSync.create", return_value=box) as create:
            env = self.provider.create_environment(cwd="/tmp", timeout=3)
        self.addCleanup(env.cleanup)
        connection = create.call_args.kwargs["connection_config"]
        self.assertEqual(connection.domain, "127.0.0.1:18080")
        self.assertEqual(connection.api_key, "fixture-only")
        self.assertTrue(connection.use_server_proxy)
        self.assertFalse(create.call_args.kwargs.get("env"))
        self.assertFalse(env.uses_host_filesystem)
        self.assertEqual(env.execute(WRITE_MARKER)["returncode"], 0)
        self.assertEqual(env.execute("read_fixture_marker")["output"], "B's synthetic marker")
        self.assertEqual(env.execute("fixture_nonzero")["returncode"], 7)
        env.cleanup()
        env.cleanup()
        self.assertEqual(box.kills, 1)
        self.assertTrue(box.closed)

    def test_remote_command_start_failure_surfaces_diagnostic(self):
        with patch("opensandbox.sync.SandboxSync.create", return_value=SyntheticSandbox()):
            env = self.provider.create_environment(cwd="/tmp", timeout=3)
        self.addCleanup(env.cleanup)
        result = env.execute("fixture_failed_to_start")
        self.assertEqual(result["returncode"], 1)
        self.assertIn("fixture failed to start", result["output"])

    def test_remote_command_disconnect_remains_infrastructure_error(self):
        with patch("opensandbox.sync.SandboxSync.create", return_value=SyntheticSandbox()):
            env = self.provider.create_environment(cwd="/tmp", timeout=3)
        self.addCleanup(env.cleanup)
        with self.assertRaisesRegex(EnvironmentConnectionError, "fixture stopped responding"):
            env.execute("fixture_transport_error")

    def _run_stream(self, events):
        payload = "".join(
            f"data: {json.dumps(dict(event, timestamp=index))}\n\n"
            for index, event in enumerate(events)
        )

        def respond(request):
            self.assertEqual((request.method, request.url.path), ("POST", "/command"))
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, text=payload)

        with httpx.MockTransport(respond) as transport:
            commands = CommandsAdapterSync(
                ConnectionConfigSync(transport=transport),
                SandboxEndpoint(endpoint="127.0.0.1:18081"),
            )
            from hermes_opensandbox_fixture.sandbox_env import OpenSandboxProcess

            process = OpenSandboxProcess(commands, "printf fixture", 3, "fixture-only")
            with process.stdout:
                output = process.stdout.buffer.read().decode("utf-8")
            return output, process.wait(3)

    def test_legacy_execd_stream_preserves_line_boundaries_and_blank_lines(self):
        output, returncode = self._run_stream([
            {"type": "stdout", "text": "first"},
            {"type": "stdout", "text": "\n"},
            {"type": "stdout", "text": "second"},
            {"type": "stdout", "text": "tail"},
            {"type": "execution_complete"},
        ])
        self.assertEqual(output, "first\n\nsecond\ntail")
        self.assertEqual(returncode, 0)

    def test_terminated_frames_and_mixed_stream_order_are_unchanged(self):
        output, returncode = self._run_stream([
            {"type": "stdout", "text": "first\n"},
            {"type": "stderr", "text": "warning\r"},
            {"type": "stdout", "text": "\n"},
            {"type": "stdout", "text": "partial"},
            {"type": "stderr", "text": "last"},
            {"type": "error", "error": {"ename": "CommandExecError", "evalue": "7", "exit_code": 7}},
        ])
        self.assertEqual(output, "first\nwarning\r\npartiallast")
        self.assertEqual(returncode, 7)

    def test_cold_create_has_separate_read_timeout_without_replaying_post(self):
        requests = []

        def no_response(_transport, request):
            requests.append((request.method, request.url.path, dict(request.extensions["timeout"])))
            raise httpx.ReadTimeout("fixture server accepted request but did not respond", request=request)

        with patch.object(httpx.HTTPTransport, "handle_request", no_response):
            with self.assertRaisesRegex(EnvironmentConnectionError, "fixture server accepted"):
                self.provider.create_environment(cwd="/tmp", timeout=3)

        self.assertEqual(requests, [
            ("POST", "/v1/sandboxes", {"connect": 10, "read": 60, "write": 10, "pool": 10}),
        ])

    def test_cold_create_timeout_does_not_change_endpoint_or_command_timeouts(self):
        box = SyntheticSandbox()
        with patch("opensandbox.sync.SandboxSync.create", return_value=box) as create:
            env = self.provider.create_environment(cwd="/tmp", timeout=3)
        self.addCleanup(env.cleanup)
        config = create.call_args.kwargs["connection_config"]
        timeouts = {}

        def respond(request):
            timeouts[request.url.path] = dict(request.extensions["timeout"])
            if request.method == "GET":
                return httpx.Response(200, json={"endpoint": "127.0.0.1:18080/execution"})
            return httpx.Response(
                200, headers={"Content-Type": "text/event-stream"},
                text='data: {"type":"execution_complete","timestamp":0,"exit_code":0}\n\n',
            )

        with httpx.MockTransport(respond) as transport:
            config = config.model_copy(update={"transport": transport})
            service = SandboxesAdapterSync(config)
            endpoint = service.get_sandbox_endpoint("fixture", 44772, True)
            commands = CommandsAdapterSync(config, endpoint)
            self.assertEqual(commands.run("printf fixture").exit_code, 0)

        self.assertEqual(timeouts["/v1/sandboxes/fixture/endpoints/44772"],
                         {"connect": 10, "read": 10, "write": 10, "pool": 10})
        self.assertEqual(timeouts["/execution/command"],
                         {"connect": 10, "read": None, "write": 10, "pool": None})

    def test_cleanup_can_retry_after_transport_failure(self):
        box = SyntheticSandbox()
        with patch("opensandbox.sync.SandboxSync.create", return_value=box):
            env = self.provider.create_environment(cwd="/tmp", timeout=3)
        self.addCleanup(env.cleanup)
        with patch.object(box, "kill", side_effect=SandboxException("network down")):
            with self.assertRaisesRegex(EnvironmentConnectionError, "network down"):
                env.cleanup()
        self.assertFalse(box.closed)
        env.cleanup()
        self.assertTrue(box.closed)

    def test_initialization_failure_destroys_allocated_sandbox_and_raises(self):
        box = SyntheticSandbox()
        with patch("opensandbox.sync.SandboxSync.create", return_value=box), \
             patch("tools.environments.base.BaseEnvironment.init_session",
                   side_effect=ValueError("initialization fixture failed")):
            with self.assertRaisesRegex(ValueError, "initialization fixture failed"):
                self.provider.create_environment(cwd="/tmp", timeout=3)
        self.assertEqual(box.kills, 1)
        self.assertTrue(box.closed)

    def test_cleanup_failure_does_not_hide_initialization_error(self):
        box = SyntheticSandbox()
        with patch("opensandbox.sync.SandboxSync.create", return_value=box), \
             patch.object(box, "kill", side_effect=SandboxException("synthetic cleanup failed")), \
             patch("tools.environments.base.BaseEnvironment.init_session",
                   side_effect=ValueError("initialization fixture failed")), \
             self.assertLogs(level="WARNING") as logs:
            with self.assertRaisesRegex(ValueError, "initialization fixture failed"):
                self.provider.create_environment(cwd="/tmp", timeout=3)
        self.assertTrue(box.closed)
        self.assertTrue(any("synthetic cleanup failed" in message for message in logs.output))

    def test_timeout_interrupts_remote_command_by_id(self):
        box = SyntheticSandbox()
        with patch("opensandbox.sync.SandboxSync.create", return_value=box):
            env = self.provider.create_environment(cwd="/tmp", timeout=1)
        self.addCleanup(env.cleanup)
        result = env.execute("fixture_cancel")
        self.assertEqual(result["returncode"], 124)
        self.assertTrue(box.interrupted.is_set())

    def test_transport_failure_raises_with_no_local_fallback(self):
        failure = SandboxException("Could not connect to private execution fixture")
        with patch("opensandbox.sync.SandboxSync.create", side_effect=failure), \
             patch("tools.terminal_tool_backends._LocalEnvironment",
                   side_effect=AssertionError("local fallback")):
            with self.assertRaisesRegex(EnvironmentConnectionError, "Could not connect"):
                _create_environment("opensandbox", "", "/tmp", 1)

    def test_rejected_key_is_distinct_and_redacted(self):
        failure = SandboxApiException("fixture-only was rejected", status_code=401)
        with patch("opensandbox.sync.SandboxSync.create", side_effect=failure):
            with self.assertRaisesRegex(EnvironmentConnectionError, "HTTP 401") as caught:
                self.provider.create_environment(cwd="/tmp", timeout=1)
        self.assertNotIn("fixture-only", str(caught.exception))

    def test_missing_key_fails_before_sandbox_creation(self):
        with patch.dict(os.environ, {"OPEN_SANDBOX_API_KEY": ""}), \
             patch("opensandbox.sync.SandboxSync.create") as create:
            with self.assertRaisesRegex(EnvironmentConnectionError, "OPEN_SANDBOX_API_KEY"):
                self.provider.create_environment(cwd="/tmp", timeout=1)
        create.assert_not_called()
