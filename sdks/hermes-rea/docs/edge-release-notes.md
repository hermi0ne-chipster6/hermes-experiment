# Hermes REA 6.9.0 Edge release notes

Published as Store revision 2 on `latest/edge` by Cody Prevost (`codyprevost`). [Publication receipt](edge-publication.json).

This edge release targets Ubuntu 26.04 on amd64. It packages REA at upstream commit `51459cf203ae1eb6b586a95b21899eaa0f631823` with a matched Frida 17.25.1 JavaScript package and Linux native addon. Stable qualification remains open.

- The full archive integrity comparison passed. A fresh Workshop reached Ready and passed all 13 installed-file identity checks.
- CLI and MCP startup passed. `tools/list` and `binary_session` agreed on all 259 tools.
- The 130-case functional run had 122 initial passes. Four ambiguous container cases passed on retry with explicit Kuna selection. Four legacy native cases passed on retry with stock Ghidra.
- Frida enumeration, instrumentation and the child-process lifecycle regression passed. SQLite and Ghidra succeeded after instrumentation in the same MCP process.

The default SDK launcher enables the NativeAOT profile, which rejects certain legacy and raw native targets. The four stock Ghidra retries used the installed REA entry point with that profile omitted. The official SDKcraft VM suite remains untested because the VPS lacks KVM. Licensed Hopper, IDA and JEB integrations, attached Android devices, and external model services need separate configuration. Prior NativeAOT, persistence and restricted SSH results remain in the acceptance record.

[Functional case results](edge-functional-results.md) · [Installed capability matrix](edge-capability-matrix.md) · [Source and format audit](capability-matrix.md)
