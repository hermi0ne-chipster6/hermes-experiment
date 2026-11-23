"""Select the OpenSandbox terminal provider with terminal.backend: opensandbox."""

from .provider import OpenSandboxProvider


def register(ctx) -> None:
    ctx.register_terminal_environment_provider(OpenSandboxProvider())
