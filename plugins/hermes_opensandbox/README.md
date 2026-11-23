# OpenSandbox terminal provider

Enable the `hermes_opensandbox` plugin and select `terminal.backend: opensandbox`
in the Hermes profile. Load the plugin in process. The provider reads
`OPEN_SANDBOX_DOMAIN` and `OPEN_SANDBOX_API_KEY` from the Workshop environment,
including the existing connected secret plug for the key. Set
`OPEN_SANDBOX_PROTOCOL=https` when the configured private endpoint serves TLS.
The domain takes a host and optional port.

The plugin creates an expiring sandbox for each Hermes environment, uses the
server proxy for command transport, and releases the sandbox on cleanup. The
sandbox image supplies Bash and the command-line programs used by Hermes's file
and code tools. The default image is the digest used by the project's OpenSandbox
workload probe. Set `terminal.opensandbox_image` to choose a different image.
Hermes's command approvals apply. The provider implements terminal, file and code
execution. Desktop streams and hosted tenant scopes are unsupported.

Keep the worker and its proxy on the private network. The control API key
authenticates sandbox lifecycle requests. Data-plane authorization follows the
worker's proxy policy independently.

The package follows Hermes v0.23.3's
[terminal provider guide](https://github.com/NousResearch/hermes-agent/blob/caafe5389ae585ef77387a962aee05b1bcf17029/website/docs/developer-guide/terminal-environment-plugin.md)
and the
[official Singularity example](https://github.com/NousResearch/hermes-official-plugins/tree/d46aced3031a8f533fdbf0806bc4cf0d0b28be07/singularity).
The provider fixture runs against that Hermes source and the OpenSandbox 1.2.0
Python client in an isolated profile. It substitutes a synthetic sandbox for the
remote service.

```sh
HERMES_HOME="$(mktemp -d)" PYTHONPATH=/path/to/hermes-agent \
  python -m unittest discover -s plugins/hermes_opensandbox/tests -v
```
