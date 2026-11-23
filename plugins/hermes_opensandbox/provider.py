"""Native Hermes terminal provider for a private OpenSandbox service."""

from datetime import timedelta
import importlib.util
import os
from urllib.parse import urlsplit

from agent.terminal_env_provider import TerminalEnvironmentProvider


_DEFAULT_IMAGE = "python@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8"
_CREATE_READ_TIMEOUT_SECONDS = 60.0


def _set_create_read_timeout(request):
    # Docker can pull the workload and execd images before sending the create
    # response. Extend only this read timeout and keep the SDK's POST retry
    # policy and ordinary command/endpoint timeouts.
    if request.method == "POST" and request.url.path == "/v1/sandboxes":
        request.extensions["timeout"]["read"] = _CREATE_READ_TIMEOUT_SECONDS


class OpenSandboxProvider(TerminalEnvironmentProvider):
    name = "opensandbox"
    display_name = "OpenSandbox"
    description = "Run commands in an ephemeral sandbox on the configured private worker."
    default_cwd = "/tmp"
    strip_env_keys = frozenset({"OPEN_SANDBOX_API_KEY"})
    # Preserve native Hermes command approvals on this backend.
    skip_container_guards = False

    def probe(self):
        if importlib.util.find_spec("opensandbox") is None:
            return "needs_setup", "Install the plugin's opensandbox Python dependency."
        if not os.environ.get("OPEN_SANDBOX_DOMAIN", "").strip():
            return "needs_setup", "Set OPEN_SANDBOX_DOMAIN to the private worker host and port."
        if not os.environ.get("OPEN_SANDBOX_API_KEY", "").strip():
            return "needs_setup", "Supply OPEN_SANDBOX_API_KEY through the Workshop secret plug."
        return "ready", ""

    def is_available(self):
        return self.probe()[0] == "ready"

    def setup_instructions(self):
        return [
            "Set OPEN_SANDBOX_DOMAIN to the private worker host and port.",
            "Supply OPEN_SANDBOX_API_KEY through the Workshop secret plug.",
            "Set terminal.opensandbox_image to override the default pinned sandbox image.",
        ]

    def create_environment(self, *, cwd, timeout, task_id="default", image=None,
                           container_config=None, **kwargs):
        from tools.environments.base import EnvironmentConnectionError

        status, detail = self.probe()
        if status != "ready":
            raise EnvironmentConnectionError(f"OpenSandbox setup is incomplete. {detail}")

        from hermes_cli.config import load_config_readonly
        from opensandbox.config.connection_sync import ConnectionConfigSync
        from opensandbox.exceptions import SandboxException
        from opensandbox.sync import SandboxSync

        from .sandbox_env import OpenSandboxEnvironment, remote_error

        terminal = load_config_readonly().get("terminal", {})
        image = image or terminal.get("opensandbox_image") or _DEFAULT_IMAGE
        config = container_config or {}
        domain = os.environ["OPEN_SANDBOX_DOMAIN"].strip()
        api_key = os.environ["OPEN_SANDBOX_API_KEY"]
        protocol = os.environ.get("OPEN_SANDBOX_PROTOCOL", "http")
        try:
            endpoint = urlsplit(f"//{domain}")
            if (not endpoint.hostname or endpoint.username is not None or endpoint.path
                    or endpoint.query or endpoint.fragment or endpoint.port == 0
                    or any(char.isspace() for char in domain)):
                raise ValueError
        except ValueError:
            raise EnvironmentConnectionError(
                "OpenSandbox requires OPEN_SANDBOX_DOMAIN as a host with an optional port."
            ) from None
        if protocol not in {"http", "https"}:
            raise EnvironmentConnectionError("OPEN_SANDBOX_PROTOCOL must be http or https.")

        connection = ConnectionConfigSync(
            domain=domain, api_key=api_key, protocol=protocol, use_server_proxy=True,
            request_timeout=timedelta(seconds=10), disable_metrics=True,
            event_hooks={"request": [_set_create_read_timeout]},
        )
        try:
            sandbox = SandboxSync.create(
                image, timeout=timedelta(hours=1), ready_timeout=timedelta(minutes=3),
                resource={"cpu": str(config.get("container_cpu", 1)),
                          "memory": f'{config.get("container_memory", 5120)}Mi'},
                connection_config=connection,
            )
        except SandboxException as exc:
            raise remote_error("create sandbox", exc, api_key) from None

        return OpenSandboxEnvironment.initialize(sandbox, api_key=api_key, cwd=cwd, timeout=timeout)
