# Hermes Experiment 1 Plugin Pack

The [native pack](hermes-pack.yaml) pins optional independent installs using
Hermes’s own plugin manager. The [catalog](catalog.yaml) records source identity,
distribution and qualification for every item considered here. Release and
pack versions are independent. The catalog’s Hermes revision records the
baseline used for these checks.

| Component | Source and distribution | Activation and observed qualification |
| --- | --- | --- |
| Hindsight | Vectorize plugin, SDK-bundled | Select the native Hindsight memory provider. The isolated embedded API runtime is packaged separately inside the SDK. Semantic recall needs its own qualification. |
| Hermes OpenTelemetry | briancaffey/hermes-otel, SDK-bundled | Enable the installed plugin using native Hermes configuration. Dashboard startup and trace retrieval are separate checks. |
| Diary and Notifications | Experiment repository, SDK-bundled | The SDK supplies the native manifests and shared diary module. Use the existing profile activation. Independent distribution is under review. |
| Buzz and email | Official Hermes core | Configure the native gateway adapters in the operator profile. The notification wrapper has synthetic adapter evidence. |
| Promise Keeper | MokiMeow/promise-keeper, independent | Native install, doctor and a synthetic rule persistence check passed at the selected pin. The runtime ignores its declared middleware field, so the check covers rule commands and persistence. |
| Mandate | JoeProAI/mandate, native catalog candidate | Native scanning of the selected pin reported caution and 89 findings, with confirmation required. Installation compatibility remains unresolved. |
| OpenSandbox | Experiment repository, independent native provider | The pinned source under `plugins/hermes_opensandbox` passed packaged registration, enable, disable and re-enable. Select the backend and configure the private worker separately. The paired runtime matrix is tracked independently. |
| Official REA plugin and skills | NousResearch/hermes-official-plugins, existing SDK provenance | The verified plugin and skills trees identify the existing 6.7.0 integration. Compatibility and admission for the 6.9.0 Workshop C candidate remain open. |

## Apply and restore

Review the exact entries with `hermes plugins pack show plugins/pack/hermes-pack.yaml`.
On a fresh profile, `hermes plugins pack install plugins/pack/hermes-pack.yaml`
requires an interactive review and enables newly installed entries after native
admission. The native manager handles dependency and capability consent.

For an existing profile, review `hermes plugins list --json` and its
`$HERMES_HOME/plugins/.install-metadata.json` before making changes. The normal
pack install leaves an existing plugin untouched. The native installer reports
already-installed entries as failed install attempts and exits nonzero when
such entries are present. Use the normal invocation to preserve their state.
The native pack's
`--force` reinstall can enable an entry again.

To install a reviewed independent entry in a disabled state, use the native
single-plugin command with the exact repository URL and commit from the catalog.
For a plugin stored in a subdirectory, append `#SUBDIRECTORY` to the Git URL.

```sh
hermes plugins install REPOSITORY --ref COMMIT --no-enable
hermes plugins doctor PLUGIN --ci
hermes plugins enable PLUGIN
hermes plugins disable PLUGIN
hermes plugins remove PLUGIN
```

Back up persistent profile configuration, plugin data and the installation
receipt before a reviewed revision change. Use `hermes plugins check-updates`
for discovery and `hermes plugins update PLUGIN` for reviewed updates supported
by the installed source. Direct exact-SHA installs report their pin and leave
it in place. Verify a new or restored direct-source pin in a disposable profile
using the exact install command above. Restore the backed-up plugin data and
recorded activation choice through the native profile. Core refresh leaves
independent plugin revisions in the persistent profile.

## Verify

From the repository root run `python3 -m unittest discover -s plugins/pack/tests -v`.
Run `python plugins/pack/tests/verify_native.py` using a disposable copy of the
pinned Hermes source and an interpreter with its frozen dependencies. Set
`PYTHONPATH` and `HERMES_INSTALL_ROOT` to that copy. A fresh native package
manager may fetch its pinned runtime inputs. The fixture uses an isolated
profile and local Git repository to check repeat resolution, a pinned checkout
after the upstream tip advances, and disabled state after a normal second
application.
