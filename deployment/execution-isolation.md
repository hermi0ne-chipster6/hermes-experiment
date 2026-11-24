# Execution isolation decision

Workshop A supports native interactive execution. Use Canonical's Docker SDK with OpenSandbox in Workshop B for explicitly remote execution. The Hermes Bubblewrap plugin is optional.

| Requirement | Separate OpenSandbox worker | Optional Hermes Bubblewrap plugin |
| --- | --- | --- |
| Preserve A/B separation | B owns the Docker daemon and workload files; A uses authenticated native MCP/API operations | Does not replace the separately approved execution worker |
| File operations | Explicit OpenSandbox calls target sandbox paths in B. Native local tools operate in A. | Bubblewrap alone must not be assumed to isolate every Hermes file tool |
| Lifecycle | Native create, bounded lifetime and kill/close APIs; command/file/proxy paths tested with a temporary sandbox | Compatibility and coverage need separate tests before adding it |
| Credential boundary | A retains model, mailbox, financial and REA credentials; B receives only its execution/tunnel credentials | An extra process sandbox does not replace credential separation |

The verified baseline is OpenSandbox's native string-command and file interface. Full browser/code-interpreter images, all discovery/cron surfaces, network policy and failure/cancellation cases still require qualification. An unavailable worker must return an error; it must not select local execution in A.

OpenSandbox's own bootstrap includes Bubblewrap-related components. Those are part of its upstream runtime, distinct from installing the Hermes Bubblewrap plugin. No additional Hermes isolation plugin was installed or claimed compatible in this run.
