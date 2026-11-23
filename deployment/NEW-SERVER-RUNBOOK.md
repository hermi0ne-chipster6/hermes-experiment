# Hermes Experiment #1: new-server implementation and acceptance plan

This is a plan to execute **on the destination server**, not evidence that the
destination already works. Complete the phases in order. Record each check as
**PASS, FAIL, BLOCKED or NOT RUN** in a private copy of
[ACCEPTANCE-RECORD.md](ACCEPTANCE-RECORD.md). A missing provider account, untested
isolation rule or unavailable secret service is BLOCKED, not PASS.

Keep the old server until the final cutover gate. This plan installs the existing
three-Workshop architecture; it does not implement an MCP gateway, move Cloudflared,
migrate memory banks, finish a wallet, or promote Store releases automatically.

## 0. Preserve the old server and collect operator inputs

Download a private off-server copy of `/home/codex/hermes-sdk-development/` from
the old server. It includes original documentation, original design records,
the three Canonical skills, raw evidence and local SDK archives omitted from Git.
Save valuable Codex history/configuration separately if wanted. Verify the backup
on another machine. Keep credentials and runtime backups encrypted and separate
from Git. Copying only the GitHub repository does not back up runtime state.

Decide which data is to be restored and which starts fresh. Preserve the existing
paid Hindsight banks wherever they currently reside. Do not restore into the only
copy or change embedding dimensions during this deployment. Memory restoration is
a separately approved phase; a fresh synthetic bank is sufficient for initial tests.

Have these values available before their respective activation phases:

| Input | Used by |
| --- | --- |
| Ubuntu 26.04 AMD64 host and a non-root account with sudo | All phases |
| Chosen model provider/model and its API credential | A, first real heartbeat |
| Dedicated sandbox API credential | A and B, same credential |
| Dedicated REA SSH identity and verified C host key | A to C |
| Operator's authenticated Buzz public key, agent identity, relay and channel | Native Buzz gateway |
| Agent mailbox, SMTP/IMAP settings, operator address and authentication rules | Native email gateway |
| Delegated subdomain and restricted tunnel configuration | Public workload test |
| Existing Hindsight backup, and any real Link/Sui identities being retained | Approved state restoration |

Missing Buzz/mail/domain information need not block package installation, but it
does block acceptance of those integrations and unattended experiment activation.

## 1. Verify the destination host

Run on the destination as the non-root account that will own all three projects:

```bash
whoami
id
cat /etc/os-release
uname -m
systemd-detect-virt
free -h
df -h /
sudo -v
```

**PASS:** Ubuntu **26.04**, `x86_64`, functioning systemd/sudo and sufficient disk/RAM.
Budget approximately 4 vCPUs, 16 GB RAM and 100 GB free SSD for deployment/testing;
these are planning allowances, not measured minimums. Browser/analysis load may
require more. No GPU is required. The provider must permit unprivileged LXD and
Docker nested inside B.

KVM is **not required for these LXD-container deployments**. Check separately if
this machine will also perform VM-based Spread qualification:

```bash
ls -l /dev/kvm
```

An absent `/dev/kvm` blocks VM qualification, not the container installation below.
Do not change the target OS or make B privileged to work around a provider restriction.

## 2. Install the host tools and clone the private repository

On a fresh host:

```bash
sudo apt-get update
sudo apt-get install git gh tmux curl jq python3-venv shellcheck sqlite3 acl
sudo snap install lxd --channel=6/stable
sudo lxd init --minimal
sudo snap install workshop --classic
snap list workshop lxd
workshop --version
sudo lxc info
```

If LXD already exists, inspect it first; do not rerun initialization or replace
its storage/network configuration blindly. Keep the host's public LXD API disabled.

For comparison, the original available checks used Workshop 0.9.9/revision 800 and
LXD 6.10.1/revision 41228. Record actual installed versions. A newer toolchain
requires successful acceptance checks, not an assumption of compatibility.

```bash
gh auth login
gh auth setup-git
gh repo clone hermi0ne-chipster6/hermes-experiment "$HOME/hermes-experiment"
cd "$HOME/hermes-experiment"
git status --short
git rev-parse HEAD
tmux new -s hermes-deploy
```

Continue inside tmux; detach with **Ctrl+B, D**, reconnect with
`tmux attach -t hermes-deploy`. This preserves shell processes across SSH loss,
not across a host reboot. Do not put actual credentials into a terminal transcript.

Initialize the variables again after opening a new shell:

```bash
HERMES_SOURCE="$HOME/hermes-experiment"
HERMES_OPERATOR="$(id -un)"
```

Run source checks before deployment:

```bash
cd "$HERMES_SOURCE"
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --only-binary=:all: --require-hashes -r ci/requirements.txt
python3 -m unittest discover -s tests -v
python3 ci/check.py
deactivate
```

**PASS:** all tests pass; inventory/configuration checks and ShellCheck pass.
GitHub already runs these checks, but this establishes a destination-host baseline.
Do not install publisher credentials or an API key just to run these tests.

## 3. Create separate deployment projects and inspect the Store versions

Keep the source repository outside all three agent-visible project directories:

```bash
sudo install -d -o "$HERMES_OPERATOR" -g "$(id -gn)" -m 0750 /srv/hermes
install -d -m 0750 /srv/hermes/a /srv/hermes/b /srv/hermes/c
cp "$HERMES_SOURCE/deployment/a/workshop.yaml.example" /srv/hermes/a/workshop.yaml
cp "$HERMES_SOURCE/deployment/b/workshop.yaml.example" /srv/hermes/b/workshop.yaml
cp "$HERMES_SOURCE/deployment/c/workshop.yaml.example" /srv/hermes/c/workshop.yaml
sdk info hermes-experiment
sdk info hermes-execution
sdk info hermes-rea
sdk info docker-ce
```

The three experiment SDKs were published on **latest/edge**, revision **1**:

| SDK | Reviewed version | Runtime check |
| --- | --- | --- |
| hermes-experiment | 0.22.5, upstream bf0203a7 | Hermes CLI |
| hermes-execution | 1.2.0 | OpenSandbox CLI/API |
| hermes-rea | 6.7.0, Ghidra 12.1.4 | Native REA MCP |
| Canonical docker-ce | SDK 29.5.1, Ubuntu 26.04 revision 13 | Actual Engine version must also be recorded |

These are the published acceptance baseline, not a permanent instruction to stay
on old software. If the channel now contains a different revision, review its
release record and required compatibility checks first. Do not invent a YAML
`revision` field or run `hermes update` to bypass the package process.

The revised A definition includes the standalone Sui and Stripe Link SDKs.
Use their Store names only after the selected releases are available there.
For disposable pre-publication checks, register the exact A, Sui and Link
archives with `sdkcraft try` and use their `try-` names. If upgrading an
existing Workshop, preserve both legacy state sources and follow the
[CLI state migration](../sdks/hermes-experiment/README.md#sui-and-stripe-link-state)
before enabling any gateways or financial operations.

The supplied definitions already put Canonical `docker-ce` **before**
`hermes-execution` in B. Keep each role's project, state and configuration separate.
Public Store consumption should not require the publisher's signing credentials;
investigate any authentication error instead of copying publication credentials.

## 4. Launch C, then B, then A with services unconfigured

```bash
workshop --project /srv/hermes/c launch c --verbose --wait-on-error
workshop --project /srv/hermes/c changes
workshop --project /srv/hermes/c tasks
workshop --project /srv/hermes/c info c

workshop --project /srv/hermes/b launch b --verbose --wait-on-error
workshop --project /srv/hermes/b changes
workshop --project /srv/hermes/b tasks
workshop --project /srv/hermes/b info b

workshop --project /srv/hermes/a launch a --verbose --wait-on-error
workshop --project /srv/hermes/a changes
workshop --project /srv/hermes/a tasks
workshop --project /srv/hermes/a info a
```

**PASS:** each launch change is Done and every Workshop is Ready with the expected
SDK versions/revisions. Ready currently means installed, not fully activated.

After **every** subsequent Workshop mutation, inspect that project's `changes`,
`tasks <CHANGE_ID>` and `info`, as above. Check `workshop warnings` as well.
If a hook fails, inspect its actual task log. With `--wait-on-error`, resolve the
cause and use the documented `--continue` or `--abort` path. Do not remove a
Workshop as a generic fix; that can destroy managed state.

## 5. Run the portable packaging and fixture checks first

Copy only these portable probes into the new projects:

```bash
cp "$HERMES_SOURCE/validation/hermes-agent/probe-installed.py" /srv/hermes/a/
cp "$HERMES_SOURCE/validation/hermes-agent/probe-native-hooks.py" /srv/hermes/a/
cp "$HERMES_SOURCE/validation/hermes-agent/original-charter-fixture.md" /srv/hermes/a/
cp "$HERMES_SOURCE/validation/hermes-agent/probe-workload.py" /srv/hermes/a/
cp "$HERMES_SOURCE/validation/hermes-execution/probe-api.py" /srv/hermes/b/
cp "$HERMES_SOURCE/validation/hermes-execution/opensandbox-probe.toml" /srv/hermes/b/
cp "$HERMES_SOURCE/validation/hermes-rea/mcp-smoke.py" /srv/hermes/c/
```

```bash
workshop --project /srv/hermes/c exec c -- sudo -u rea /usr/local/bin/hermes-rea-stdio --version
workshop --project /srv/hermes/c exec c -- java -version
workshop --project /srv/hermes/c exec c -- python3 /project/mcp-smoke.py
workshop --project /srv/hermes/b exec b -- docker version
workshop --project /srv/hermes/b exec b -- cloudflared --version
workshop --project /srv/hermes/b exec b -- /var/lib/workshop/sdk/hermes-execution/bin/python -I /project/probe-api.py
workshop --project /srv/hermes/a exec a -- /var/lib/workshop/sdk/hermes-experiment/bin/python -I /project/probe-installed.py
workshop --project /srv/hermes/a exec a -- /var/lib/workshop/sdk/hermes-experiment/bin/python -I /project/probe-native-hooks.py
```

**PASS:** REA reports 6.7.0 and a nonempty native tool list (207 in the baseline);
Java is 25; Docker's client/server work; Cloudflared reports 2026.10.7; B's temporary
API returns health 200, unauthenticated list 401 and authenticated list 200; A's
installed-runtime and native local-fixture assertions pass.

Run A's `probe-installed.py` **before configuring its read-only mount**: it checks
that an unconfigured chat is refused. The native-hook fixture uses an isolated
profile and local fake model API. It does not prove semantic Hindsight recall,
real provider behavior, operator approvals or production worker routing.

Do **not** run the old `validation/probe-coordinator*.py` or
`validation/probe-ssh-boundaries.py` unchanged: they contain old instance names,
addresses or `/tmp` paths. Do not use B's old `probe-workload.py`; its argv-style
command path was not supported. The A-side probe above uses the tested string form.

## 6. Install the external diary on the host

The diary database belongs outside A/B/C under its own host identity:

```bash
sudo useradd --system --home-dir /var/lib/hermes-diary --shell /usr/sbin/nologin hermes-journal
sudo install -d -o root -g root -m 0755 /opt/hermes-experiment/diary
sudo cp -a "$HERMES_SOURCE/diary/hermes_diary" /opt/hermes-experiment/diary/
sudo chown -R root:root /opt/hermes-experiment/diary
sudo install -m 0644 "$HERMES_SOURCE/deployment/diary-writer.service" /etc/systemd/system/diary-writer.service
sudo install -m 0644 "$HERMES_SOURCE/deployment/diary-control.service" /etc/systemd/system/diary-control.service
sudo usermod -aG hermes-journal "$HERMES_OPERATOR"
sudo systemctl daemon-reload
sudo systemctl enable --now diary-writer.service diary-control.service
sudo systemctl status diary-writer.service diary-control.service --no-pager
sudo stat -c '%a %U:%G %n' /run/hermes-diary /run/hermes-diary/agent.sock /run/hermes-diary/control.sock
```

If the system account already exists, inspect it instead of recreating it.
Reconnect your SSH session so the new group membership takes effect, then verify
`id`. The runtime directory should be 0750, agent socket 0660 and control socket
0600. The operator may traverse the runtime directory through the journal group;
the database directory remains private to `hermes-journal`/root.

```bash
workshop --project /srv/hermes/a connect a/hermes-experiment:diary a/system:diary
workshop --project /srv/hermes/a connections a
workshop --project /srv/hermes/a exec a -- hermes-diary health
workshop --project /srv/hermes/a exec a -- test ! -e /run/hermes-diary/control.sock
workshop --project /srv/hermes/a exec a -- test ! -e /var/lib/hermes-diary/journal.sqlite3
```

**PASS:** A reaches the writer through its guest socket, while the control socket
and database remain absent. Never tunnel `control.sock`, mount the database into
an agent, or loosen its permissions to solve a connection failure.

## 7. Attach operator-controlled configuration

Create nonsecret, root-owned host directories and files:

```bash
sudo install -d -o root -g root -m 0755 /srv/hermes/config/a /srv/hermes/config/b /srv/hermes/config/c /srv/hermes/charter/a
sudo install -o root -g root -m 0644 "$HERMES_SOURCE/deployment/a/config.yaml.example" /srv/hermes/config/a/config.yaml
sudo install -o root -g root -m 0644 "$HERMES_SOURCE/deployment/a/gateway.env.example" /srv/hermes/config/a/gateway.env
sudo install -o root -g root -m 0644 "$HERMES_SOURCE/deployment/a/original-charter.md.example" /srv/hermes/charter/a/original-charter.md
sudo install -o root -g root -m 0644 "$HERMES_SOURCE/deployment/b/opensandbox.toml.example" /srv/hermes/config/b/opensandbox.toml
sha256sum /srv/hermes/charter/a/original-charter.md
```

The charter checksum must be
`fab40f6dc5d2416db23e43d83de97c3b59db52c3d2e7bf01c051a7d9bbefd897`.
Keep only the verbatim charter in `/srv/hermes/charter/a`. Keep upstream SOUL
unchanged. For an upgrade, preserve the same charter in the old configuration
directory for rollback and follow the [CLI state cutover](../sdks/hermes-experiment/README.md#sui-and-stripe-link-state).
Leave gateway, execution and Cloudflare activation markers absent and all MCP
allowlists empty.

Stop before remounting these already-populated configuration directories:

```bash
workshop --project /srv/hermes/a stop a
workshop --project /srv/hermes/a remount a/hermes-experiment:configuration /srv/hermes/config/a
workshop --project /srv/hermes/a remount a/hermes-experiment:charter /srv/hermes/charter/a
workshop --project /srv/hermes/a start a
workshop --project /srv/hermes/b stop b
workshop --project /srv/hermes/b remount b/hermes-execution:configuration /srv/hermes/config/b
workshop --project /srv/hermes/b start b
workshop --project /srv/hermes/c stop c
workshop --project /srv/hermes/c remount c/hermes-rea:configuration /srv/hermes/config/c
workshop --project /srv/hermes/c start c
```

Inspect changes/tasks/info after each mutation. A plain start or unchanged refresh
does not necessarily rerun `setup-project`; explicitly apply the packaged hooks:

```bash
workshop --project /srv/hermes/a exec a -- env SDK=/var/lib/workshop/sdk/hermes-experiment bash /var/lib/workshop/sdk/hermes-experiment/sdk/hooks/setup-project
workshop --project /srv/hermes/b exec b -- env SDK=/var/lib/workshop/sdk/hermes-execution bash /var/lib/workshop/sdk/hermes-execution/sdk/hooks/setup-project
workshop --project /srv/hermes/c exec c -- env SDK=/var/lib/workshop/sdk/hermes-rea bash /var/lib/workshop/sdk/hermes-rea/sdk/hooks/setup-project
workshop --project /srv/hermes/a exec a -- findmnt --target /etc/hermes-experiment/config.yaml
workshop --project /srv/hermes/a exec a -- findmnt --target /project/.hermes-charter/original-charter.md
workshop --project /srv/hermes/a exec a -- readlink -f /home/workshop/.hermes/config.yaml
workshop --project /srv/hermes/a exec a -- readlink -f /project/.hermes.md
```

Check that both mounts are read-only, A's `.hermes.md` resolves to
`/project/.hermes-charter/original-charter.md` and services remain inactive
without activation markers.
Run A's hook as the default `workshop` user, not root, because it manages that
user's home and systemd session.

## 8. Establish real hostnames and the private bridge

```bash
workshop --project /srv/hermes/a info a
workshop --project /srv/hermes/b info b
workshop --project /srv/hermes/c info c
sudo lxc network show workshopbr0
sudo lxc list --all-projects
```

Record actual hostnames, addresses, LXD project and instance names. Do not reuse
this server's instance IDs or assume example DNS names match the destination.
Set the following to the hostnames actually shown by `workshop info`:

```bash
HERMES_B_HOST=REPLACE_WITH_B_HOSTNAME
HERMES_C_HOST=REPLACE_WITH_C_HOSTNAME
export HERMES_B_HOST HERMES_C_HOST
workshop --project /srv/hermes/a exec a -- getent hosts "$HERMES_B_HOST" "$HERMES_C_HOST"
sudoedit /srv/hermes/config/a/gateway.env
```

Set `OPEN_SANDBOX_DOMAIN=<B hostname>:8080` and `HERMES_REA_HOST=<C hostname>`.
These settings are nonsecret. The normal pattern is A initiating B TCP/8080 and
C TCP/22. A must not receive a Docker socket or any B/C writable state mount.

**Isolation gate:** apply a host-supported LXD NIC/profile/network policy that
permits the required flows and blocks workload access to A, host administration,
Docker, diary control and unrelated private services. This repository does not
ship a universally applicable, tested host ACL policy. Use the actual destination
NIC/profile layout and test it before autonomous execution. Do not attach extra
NICs or turn on privileged containers. Recheck the policy after refresh/reboot.

**PASS:** required DNS/bridge flows work and forbidden flows fail. Ping alone is
not this test. Record policy configuration and observed allow/deny results.

## 9. Configure credential delivery and prove it works unattended

The supplied secret slots use the operator's freedesktop Secret Service. Installing
`libsecret-tools` alone does not create an unlocked keyring or a usable session bus.
The officially documented route assumes a session running a keyring service:

```bash
sudo apt-get install libsecret-tools gnome-keyring dbus-user-session
systemctl --user status dbus.service --no-pager
busctl --user list
```

Use the host's supported login/keyring setup and confirm `org.freedesktop.secrets`
is available. `gnome-keyring-daemon --unlock` can read the login-keyring password
from protected stdin; never put that password in an argument, script or project
file. Do not replace a keyring that already holds operator credentials.

**Headless gate:** the exact service/session arrangement must work for the
Workshop owner, after SSH logout, for a persistent gateway and for the root cron
runner entering through that owner's Workshop client. After a reboot, a locked
keyring normally needs unlocking before dependent services can work. Do not call
this zero-touch reboot recovery. If that cannot be established, unattended
activation is BLOCKED pending an approved headless credential-delivery solution.

Store values using the prompts; commands contain only lookup attributes:

```bash
secret-tool store --label='Hermes model provider' application hermes-experiment-1 credential model-key
secret-tool store --label='Hermes sandbox API' application hermes-experiment-1 credential sandbox-api-key
secret-tool lookup application hermes-experiment-1 credential model-key >/dev/null
secret-tool lookup application hermes-experiment-1 credential sandbox-api-key >/dev/null
```

Each lookup must succeed and identify exactly one item. Do not use `secret-tool
search` without discarding its secret output. Use a dedicated high-entropy sandbox
credential, not a reused account password. A and B's slots intentionally select
the same item.

```bash
workshop --project /srv/hermes/a connect a/hermes-experiment:model-key a/system:model-key
workshop --project /srv/hermes/a connect a/hermes-experiment:sandbox-api-key a/system:sandbox-api-key
workshop --project /srv/hermes/b connect b/hermes-execution:api-key b/system:api-key
workshop --project /srv/hermes/a connections a
workshop --project /srv/hermes/b connections b
workshop --project /srv/hermes/a exec a -- sh -c 'workshopctl get-secret hermes-experiment.model-key | wc -c'
workshop --project /srv/hermes/b exec b -- sh -c 'workshopctl get-secret hermes-execution.api-key | wc -c'
```

**PASS:** the manual connections exist and nonzero byte counts are returned with
no secret printed. Any process in a Workshop can request its connected secrets;
connect only credentials assigned to that role. Never share the operator's full
SSH agent or give B/C the model, mailbox or wallet credentials.

Workshop's `exec --env VARIABLE` route can support a single manual validation
command using a credential already in the host environment. It does not configure
credentials for persistent services or cron, and is not a substitute for this gate.

## 10. Configure restricted REA SSH and verify current MCP

Generate a dedicated **transport-only** key on the host, outside every mounted
project. The packaged noninteractive transport requires a key it can load without
a passphrase prompt; protect it through the host keyring and encrypted backups:

```bash
install -d -m 0700 "$HOME/.local/share/hermes-operator/keys"
ssh-keygen -t ed25519 -N '' -C hermes-rea-transport -f "$HOME/.local/share/hermes-operator/keys/rea"
secret-tool store --label='Hermes REA transport' application hermes-experiment-1 credential rea-ssh-key < "$HOME/.local/share/hermes-operator/keys/rea"
sudo install -o root -g root -m 0644 "$HOME/.local/share/hermes-operator/keys/rea.pub" /srv/hermes/config/c/rea_authorized_keys
workshop --project /srv/hermes/c exec c -- env SDK=/var/lib/workshop/sdk/hermes-rea bash /var/lib/workshop/sdk/hermes-rea/sdk/hooks/setup-project
workshop --project /srv/hermes/a connect a/hermes-experiment:rea-ssh-key a/system:rea-ssh-key
```

Do not overwrite an existing key at that path. The private key stays out of C.
Capture C's **public host identity through the trusted operator interface**:

```bash
workshop --project /srv/hermes/c exec --uid 0 c -- cat /etc/ssh/ssh_host_ed25519_key.pub > "$HOME/.local/share/hermes-operator/keys/c-host.pub"
ssh-keygen -lf "$HOME/.local/share/hermes-operator/keys/c-host.pub"
printf '%s ' "$HERMES_C_HOST" | sudo tee /srv/hermes/config/a/rea_known_hosts >/dev/null
sudo tee -a /srv/hermes/config/a/rea_known_hosts < "$HOME/.local/share/hermes-operator/keys/c-host.pub" >/dev/null
sudo chmod 0644 /srv/hermes/config/a/rea_known_hosts
export HERMES_REA_HOST="$HERMES_C_HOST"
workshop --project /srv/hermes/a exec --env HERMES_REA_HOST a -- /usr/local/bin/hermes-rea-remote
```

In that running stdio session, paste the following JSON one line at a time; wait
for each matching response. Finish with Ctrl+D. These requests make no tool call:

```json
{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"operator-acceptance","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"operator-acceptance","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}
```

**PASS:** real A→C SSH/stdio returns MCP `2026-07-28` discovery and a nonempty
native REA tool list. The earlier local C probe tested a legacy handshake; both
are useful, and neither alone proves actual binary analysis.

Using a disposable acceptance credential, also verify wrong-host-key rejection,
arbitrary-command rejection, denial of PTY/port/agent forwarding, cancellation and
key revocation. Reapply C's setup hook after changing/revoking its public allowlist;
an unchanged refresh can otherwise be a no-op. Reconfirm the real host identity
after updates; do not replace it with an unverified `ssh-keyscan` result.

## 11. Start B and check real A→B execution

After the credential and network gates pass:

```bash
sudo touch /srv/hermes/config/b/execution.enabled
workshop --project /srv/hermes/b exec --uid 0 b -- install -d -m 0700 /var/lib/hermes-sandbox-work
workshop --project /srv/hermes/b exec b -- systemctl --user start opensandbox.service
workshop --project /srv/hermes/b exec b -- systemctl --user status opensandbox.service --no-pager
workshop --project /srv/hermes/a exec a -- curl -fsS "http://$HERMES_B_HOST:8080/health"
workshop --project /srv/hermes/a exec a -- curl -sS -o /dev/null -w '%{http_code}\n' "http://$HERMES_B_HOST:8080/v1/sandboxes"
```

**PASS:** health succeeds and the request without a credential returns 401.
Keep Cloudflare disabled. No public forwarding to this administrative API is allowed.

Use the portable A-side workload probe. It receives credentials over stdin, not
arguments or project files; do not enable shell tracing or print the environment:

```bash
export OPEN_SANDBOX_DOMAIN="$HERMES_B_HOST:8080"
export OPEN_SANDBOX_API_KEY="$(secret-tool lookup application hermes-experiment-1 credential sandbox-api-key)"
jq -n '{api_key:env.OPEN_SANDBOX_API_KEY,domain:env.OPEN_SANDBOX_DOMAIN}' | workshop --project /srv/hermes/a exec a -- /var/lib/workshop/sdk/hermes-experiment/bin/python -I /project/probe-workload.py
unset OPEN_SANDBOX_API_KEY
```

This pulls a pinned small acceptance image and runs synthetic command/file work
inside B. It should print `python_stdout: "42"`, a file checksum and
`server_proxy: true`, then destroy the temporary sandbox.

Record the result for A→B separately. Any reviewed A→C fixture uses an
independent benign input staged in C.

Also qualify the pinned code-interpreter/browser workload images from
`sources.json`, including cancellation, TTL cleanup and failure handling. The small
Python-image probe does not establish browser/code-interpreter acceptance. Confirm
that a sandbox cannot reach A's services, host management or other sandboxes'
private data. If B is unavailable, Hermes must not fall back to executing locally.

## 12. Verify tool selection in the active Hermes profile

For the standalone OpenSandbox MCP diagnostic, repeat the discovery and list
requests from phase 10. Supply only the dedicated sandbox key through
`exec --env`:

```bash
export OPEN_SANDBOX_API_KEY="$(secret-tool lookup application hermes-experiment-1 credential sandbox-api-key)"
workshop --project /srv/hermes/a exec --env OPEN_SANDBOX_API_KEY --env OPEN_SANDBOX_DOMAIN a -- /usr/local/bin/opensandbox-mcp --use-server-proxy
unset OPEN_SANDBOX_API_KEY
```

**PASS:** current-protocol discovery/list succeeds (19 tools in the baseline).
Use the returned schemas for real synthetic calls: `sandbox_create`, `command_run`,
`file_write`, `file_read` and `sandbox_kill`. Pass `command_run.command` as a
string and verify cleanup after success and failure.

For the Hermes terminal integration, review the exact native OpenSandbox
provider pin in the [Plugin Pack](../plugins/pack/README.md). Select
`terminal.backend: opensandbox` only in the profile intended to use the
private worker. Use `OPEN_SANDBOX_DOMAIN` and the connected `sandbox-api-key`
plug. Verify a synthetic command runs inside B and an explicit remote
operation fails visibly during an outage. In a local profile, verify
native terminal, file, browser and code tools inside A.

Review tool selections for Buzz, email and cron individually in the active
Hermes profile. Apply MCP allowlists only to the configured MCP servers. Leave
Link's allowlist empty until its separate financial acceptance gate passes.
The existing REA SSH/stdio route and the proposed private Streamable HTTP route
have separate acceptance evidence. Qualify the selected A→C route before
changing it.

Tool filtering in Hermes is client-side exposure control. It is not a per-agent
OAuth authorization boundary. No MCP OAuth gateway is implemented by this plan.

## 13. Configure Hindsight, provider settings and the native dashboard

Edit `/home/workshop/.hermes/config.yaml` for the default profile, or edit the
selected named profile's `config.yaml`. Set `model.provider` and `model.default`
to a provider and model available to your account. Set the matching allowed provider variable
name in `gateway.env` (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
or `NOUS_API_KEY`), never the key value. Preserve your profile's tool selections.

```bash
sudoedit /srv/hermes/config/a/gateway.env
export HERMES_PROVIDER_KEY_ENV=OPENROUTER_API_KEY
workshop --project /srv/hermes/a exec --env HERMES_PROVIDER_KEY_ENV a -- hermes memory setup
workshop --project /srv/hermes/a exec --env HERMES_PROVIDER_KEY_ENV a -- hermes memory status
```

Set the exported variable to the same provider-variable **name** chosen in
`gateway.env`; it contains no credential. Ordinary `workshop exec` commands do
not load that file automatically. The gateway unit and heartbeat entrypoint do.

Choose Hindsight's native **local_embedded** mode, extraction provider/model and
credential handling explicitly. The default cloud mode is not equivalent. Do not
add a second Hindsight daemon; the native manager starts the packaged backend on
demand. The pg0 data link should resolve under the durable Hindsight mount:

```bash
workshop --project /srv/hermes/a exec a -- readlink -f /home/workshop/.pg0
workshop --project /srv/hermes/a exec a -- findmnt --target /home/workshop/.hindsight
```

Check that native setup writes to the selected persistent profile. The
read-only Workshop configuration mount supplies the initial seed and
operator-managed files such as `gateway.env`.

Use a fresh test bank. Retain a unique synthetic fact, terminate the session,
start a separate session and ask for semantic recall without putting the fact
into its prompt. Repeat after A restarts and after a reviewed refresh. Record the
bank/profile, model, embedding dimensions and actual recall result. This stage can
incur your normal model/embedding charges; bound the first tests.

Restore existing banks only with separate operator approval and a consistent
backup/rollback. Native memory setup may persist credentials in its profile state;
protect and encrypt that state. MemPalace remains an evaluation candidate, not an
automatic migration target.

For telemetry, use the included plugin and native Hermes dashboard:

```bash
workshop --project /srv/hermes/a exec a -- hermes dashboard --help
```

The plugin provides an OTel tab and local live SQLite store under Hermes home;
configure no external exporter unless intended. Review content-capture settings,
since full capture can contain prompts and tool data. Use an authenticated private
admin access path; do not publish the dashboard or control plane through the
agent's disposable public subdomain. Verify a bounded real test produces a trace,
then confirm the OTel tab reads it. Add no replacement dashboard stack by default.

## 14. Configure and test native Buzz/email messaging

Populate only actual nonsecret relay/channel/operator identity and SMTP/IMAP
settings in `/srv/hermes/config/a/gateway.env`. Set the adapter configuration
flags in `config.yaml`. Keep `BUZZ_ALLOW_ALL_USERS=false` and
`EMAIL_TRUST_FROM_HEADER=false`. Email sender identity must be authenticated using
the configured mail system's trusted authentication information, not From alone.

```bash
secret-tool store --label='Hermes agent Buzz identity' application hermes-experiment-1 credential buzz-key
secret-tool store --label='Hermes agent mailbox' application hermes-experiment-1 credential email-password
workshop --project /srv/hermes/a connect a/hermes-experiment:buzz-key a/system:buzz-key
workshop --project /srv/hermes/a connect a/hermes-experiment:email-password a/system:email-password
sudoedit /srv/hermes/config/a/gateway.env
sudoedit /srv/hermes/config/a/config.yaml
```

After the previous gates pass, enable and start the persistent native gateway:

```bash
sudo touch /srv/hermes/config/a/gateway.enabled
workshop --project /srv/hermes/a exec a -- systemctl --user start hermes-gateway.service
workshop --project /srv/hermes/a exec a -- systemctl --user status hermes-gateway.service --no-pager
workshop --project /srv/hermes/a exec a -- journalctl --user -u hermes-gateway.service -n 60 --no-pager
```

Review logs privately before sharing. Test, and save evidence for:

1. Agent→operator notification and operator→agent reply on Buzz and email.
2. An unauthorized operator identity is rejected; spoofed email From is rejected.
3. A native approval request is bound to its actual operation/session; approval
   and denial both work, and a stale/unrelated reply cannot authorize it.
4. Sessions, memory and native cron remain available with the restricted toolsets.
5. Gateway restart/reconnect preserves expected session behavior.

Use harmless synthetic operations. No ACP adapter or auto-approve mode is part of
this deployment. Messaging approval never replaces transaction-specific controls.

## 15. Test one real heartbeat, then install the two-hour schedule

Install the fixed operator-owned entrypoint. Edit its `runuser -u admin` account
to the Workshop owner recorded earlier; keep the actual `/srv/hermes/a` path:

```bash
sudo install -d -o root -g root -m 0755 /opt/hermes-experiment/deployment
sudo install -o root -g root -m 0755 "$HERMES_SOURCE/deployment/enter-heartbeat" /opt/hermes-experiment/deployment/enter-heartbeat
sudoedit /opt/hermes-experiment/deployment/enter-heartbeat
```

Run the exact host-side heartbeat once, before creating a cron entry:

```bash
cd /opt/hermes-experiment/diary
sudo /usr/bin/python3 -m hermes_diary.heartbeat --socket /run/hermes-diary/control.sock --lock /run/hermes-heartbeat.lock --timeout 5400 --closing-command /opt/hermes-experiment/deployment/enter-heartbeat -- /opt/hermes-experiment/deployment/enter-heartbeat
```

**PASS:** output says `status: complete`, exit status is zero, and the matching
agent-authored diary receipt exists. Inspect it through the guest writer interface:

```bash
workshop --project /srv/hermes/a exec a -- hermes-diary read --limit 20
workshop --project /srv/hermes/a exec a -- hermes-diary commitments
```

The report must describe actual objectives, activity, outcomes, unfinished work
and all outstanding commitments. Test a harmless synthetic commitment from open
through fulfilled with an evidence reference. Fulfillment remains an agent-reported
claim. Missing/malformed reports and interrupted runs must remain incomplete;
the single bounded closing attempt must not invent activity. Verify overlap
prevention while the persistent gateway is running.

Only after those checks pass:

```bash
timedatectl status
sudo timedatectl set-timezone Etc/UTC
sudo apt-get install cron
sudo install -o root -g root -m 0644 "$HERMES_SOURCE/deployment/heartbeat.cron.example" /etc/cron.d/hermes-heartbeat
sudo systemctl enable --now cron
sudo cat /etc/cron.d/hermes-heartbeat
```

The entry uses `0 */2 * * *`, not a permanently running autonomous loop. It gives
the agent no prescribed objectives; the original charter remains authoritative.
Verify the host clock/timezone and actual executions. Record at least two scheduled
heartbeats, approximately two hours apart, including their diary receipts. An
interactive manual run alone does not prove cron credentials or lifecycle work.

## 16. Finish the remaining integrations without weakening boundaries

**Cloudflare:** the current SDK includes Cloudflared in B because workload sites
and APIs were expected there. It is not an OpenSandbox dependency, and its
placement remains an open architecture review item. Keep it disabled while that
decision is unresolved. If retaining this placement, configure only the delegated
subdomain and workload route, then store the dedicated tunnel credential:

```bash
secret-tool store --label='Hermes workload tunnel' application hermes-experiment-1 credential dedicated-tunnel-token
workshop --project /srv/hermes/b connect b/hermes-execution:cloudflare-token b/system:cloudflare-token
```

Complete the real Cloudflare ingress/DNS configuration before creating
`/srv/hermes/config/b/cloudflare.enabled` and starting `cloudflared.service`.
The packaged client/unit do not create routes or DNS records. A normal zone DNS
token is not constrained to an arbitrary single subdomain: use actual delegation
or preconfigured restricted routes. Test a synthetic website/API from outside
the host and prove OpenSandbox, REA, SSH, Docker and diary administration remain
unreachable. Do not point a public route at OpenSandbox's administrative proxy.

**Stripe Link/Sui:** verify installed CLI versions and preserve native identity
locations and policy controls. Keep their real operations disabled until the
actual Link transaction policy and required Sui **2-of-3 multisignature** are
configured and tested through approved simulation/fixtures. This runbook does not
fund or initialize a wallet or authorize a transaction. Native credentials and
wallet recovery material need separate encrypted backups. If these requirements
remain unfinished, record that explicitly; package Ready is not financial acceptance.

## 17. Prove persistence, restart recovery and backups

First export any B workload artifacts that matter. B's Docker workload files and
running sandboxes are not promised to survive refresh; recreate workloads as
needed. Its control DB, A's state/Hindsight/Link/Sui mounts, C's analysis state
and the external host diary have different persistence contracts.

Record a harmless persistence marker in A:

```bash
workshop --project /srv/hermes/a exec a -- sh -c 'printf "acceptance-state\n" > /home/workshop/.hermes/acceptance-state'
workshop --project /srv/hermes/a info a
workshop --project /srv/hermes/b info b
workshop --project /srv/hermes/c info c
```

Before any refresh, inspect Store channels again and approve any changed revision.
Then test each role separately, inspecting changes/tasks/info and warnings:

```bash
workshop --project /srv/hermes/c refresh c --verbose --wait-on-error
workshop --project /srv/hermes/b refresh b --verbose --wait-on-error
workshop --project /srv/hermes/a refresh a --verbose --wait-on-error
workshop --project /srv/hermes/a exec a -- cat /home/workshop/.hermes/acceptance-state
workshop --project /srv/hermes/a connections a
workshop --project /srv/hermes/b connections b
```

An unchanged refresh may perform no rebuild. Record whether the test was a no-op
or an actual refresh; a no-op does not prove survival of filesystem replacement.
Also stop/start each role and verify the same data after a controlled host reboot.
Confirm hostnames/SSH fingerprints, read-only mounts, secret connections, bridge
ACLs, gateway, actual memory recall, diary and cron again. Reconnect interfaces
explicitly if their definitions changed. Verify credential availability after SSH
logout and after the host's supported keyring-unlock procedure following reboot.

Create an online-consistent host diary backup with SQLite's backup operation:

```bash
sudo install -d -o root -g root -m 0700 /srv/hermes/backups
sudo sqlite3 /var/lib/hermes-diary/journal.sqlite3 '.backup /srv/hermes/backups/diary-acceptance.sqlite3'
sudo sqlite3 /srv/hermes/backups/diary-acceptance.sqlite3 'PRAGMA integrity_check;'
```

Use a fresh backup filename on subsequent runs. Copy backups off-host securely
and restore-test a copy. For Hindsight/PostgreSQL, use its native consistent
backup/export procedure, or stop A and verify all its embedded processes are
stopped before copying the durable state. Do not copy a live PostgreSQL directory
and call it a consistent backup. Record the actual mount host-source locations
from `workshop info`, including keyring/identity state outside the projects.

## 18. Run separate stable-release qualification when KVM is available

On a dedicated disposable Ubuntu 26.04 AMD64 KVM host, install the reviewed
Workshop/SDKcraft/LXD toolchain, register an online GitHub Actions runner with
labels `self-hosted`, `linux`, `x64`, `hermes-sdk-build`, and use a current runner
supporting the workflows' Node 24 actions. Do not register the production agent
server as this privileged CI runner.

Dispatch **SDK packaging qualification** from `main` with `runner_ready=true`
only after verifying that host. The default false value intentionally blocks
before queuing SDK jobs:

1. In the private repository, open **Settings → Actions → Runners → New
   self-hosted runner**. Follow GitHub's current Linux x64 registration commands
   on the disposable host and add the `hermes-sdk-build` label.
2. Confirm the runner is **Online/Idle** and its account has the required build
   privileges. Keep registration tokens out of logs and source files.
3. From your authenticated source checkout, dispatch and inspect the run:

```bash
gh workflow run sdk-qualification.yml --repo hermi0ne-chipster6/hermes-experiment --ref main -f runner_ready=true
gh run list --repo hermi0ne-chipster6/hermes-experiment --workflow sdk-qualification.yml --limit 3
```

Open the new run in GitHub, or use `gh run view <RUN_ID>` and
`gh run watch <RUN_ID> --exit-status`. Inspect all three SDK matrix jobs and
download their qualification artifacts before the seven-day retention expires.
The workflow performs `sdkcraft clean`, `sdkcraft try --build-for amd64`,
`sdkcraft test --list` and `sdkcraft test` separately under each `sdks/<name>/`
directory. For a manual run, follow those same commands and preserve their
per-SDK output; do not combine the results into one generic success claim.

Record results individually: A launch, A persistence, A missing-secret, B launch
and C launch. All must actually pass; a missing KVM host is BLOCKED. Preserve
tested SDK bytes/checksums and evidence before deleting the temporary test host.
These smoke results do not replace the application integration gates above.
Promote exact tested Store revisions only after operator review; no runtime
`hermes update` or unreviewed dependency upgrades are part of deployment.

## 19. Final cutover and permission to erase the old server

Keep `/etc/cron.d/hermes-heartbeat` active on only the accepted host, so both servers
cannot independently start the same experiment. Document which host owns each
identity, mailbox, tunnel and state store. Confirm no duplicate gateway/tunnel is
still using the same credentials on the old host.

**The old server can be retired only after:**

- Original documentation, skills, valuable history and runtime/identity backups
  exist off the old server and a restore test has succeeded.
- A/B/C installation and required application integration checks are PASS, with
  explicit evidence for cross-worker execution, REA analysis, memory, diary and
  commitments, native authenticated messaging and actual two-hour scheduling.
- Required domain/financial features are accepted, or the operator has explicitly
  approved a restricted cutover with those features disabled and their data preserved.
- A controlled refresh/restart/reboot test has succeeded, with no local execution
  fallback or lost access boundaries. State host-source locations are recorded.
- Every remaining FAIL/BLOCKED/NOT RUN item has a named resolution or explicit
  operator deferral. If stable release is claimed, its separate KVM qualification
  and review have also passed.

Keep the evidence private. Do not equate a green source-CI job, Ready status, a
successful model response or a zero process exit with completion of this checklist.

## References

- [Existing activation checklist](activation-checklist.md) and [network contract](networking.md)
- [Recorded baseline and outstanding gates](../reports/verification.md)
- [Workshop installation](https://ubuntu.com/workshop/docs/tutorial/part-1-get-started/)
- [Workshop CLI, including remount](https://ubuntu.com/workshop/docs/reference/cli/workshop/)
- [Workshop secret delivery prerequisites](https://ubuntu.com/workshop/docs/how-to/develop-with-workshops/provide-secrets/)
- [Ubuntu secret-tool manual](https://manpages.ubuntu.com/manpages/resolute/man1/secret-tool.1.html)
- [Ubuntu keyring daemon manual](https://manpages.ubuntu.com/manpages/resolute/man1/gnome-keyring-daemon.1.html)
- [Pinned native OTel dashboard documentation](https://github.com/briancaffey/hermes-otel/blob/d234865b13e997e0b3a50dc18aaad7c7d7b1b1fe/website/docs/dashboard.md)
