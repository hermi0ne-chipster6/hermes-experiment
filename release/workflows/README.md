# Maintenance workflows

Active definitions live in `.github/workflows/`; the former Hermes-only templates
have been replaced. See [maintenance instructions](../README.md).

- `checks.yml`: tests, inventory/configuration validation, ShellCheck, actionlint
  and history secret scanning on pushes and pull requests.
- `releases.yml`: official-source metadata monitoring every six hours and on
  relevant main-branch updates; retains JSON and Markdown review artifacts.
- `sdk-qualification.yml`: manual packaging/Spread checks on the reviewed main
  branch, after the operator verifies the dedicated KVM runner is online.

Lightweight hosted jobs use Ubuntu 24.04. Every SDK target and the full build
host remain **Ubuntu 26.04 AMD64**. No Store or production credentials are used.
The current LXD-container deployment does not require KVM; KVM is needed for the
VM-based qualification suite, which may run on a separate temporary host.

The `hermes-sdk-build` runner must be disposable, restricted to trusted operators,
and have Workshop/SDKcraft/LXD, passwordless build privileges, usable KVM and
adequate disk/RAM. Do not register the production agent VPS as this privileged
runner. Keep GitHub Actions usage within the account's configured allowance.

The readiness input is an operator acknowledgment, not remote discovery of runner
health. A stale acknowledgment can leave jobs queued; verify online status before
dispatch. The default false input fails preflight promptly and queues no SDK jobs.

Green hosted checks or Spread smoke jobs do not establish full A/B/C integration
or authorize promotion. Missing, failed and skipped acceptance gates remain open.
