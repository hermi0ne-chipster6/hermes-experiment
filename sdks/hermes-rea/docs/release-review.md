# Review and proposed release procedure

The SDK Store approved revision 2 and assigned it to `latest/edge`. See the [publication receipt](edge-publication.json) and [release notes](edge-release-notes.md). Stable qualification remains open.

## Review inputs

- Existing SDK identity: `hermes-rea`, publisher `codyprevost`; revision 2/version 6.9.0 on `latest/edge`. Revision 1/version 6.7.0 is the historical baseline.
- Development branch: `dev/hermes-rea-full-parity`, based on original repository commit `df4d649`.
- Unmodified REA baseline: `51459cf203ae1eb6b586a95b21899eaa0f631823`, package version6.9.0. This is newer than the npm6.9.0 release commit, so the commit and source manifest are part of the compatibility contract.
- Read the final validation report, capability matrix and exact test evidence together. Successful registration, source-integrity checks and client version probes are distinct from successful provider operations.
- Inspect `git diff` in the original repository. Added files are included through intent-to-add index entries; earlier source and Git history remain available.
- Review `SOURCE.json`, dependency locks, source-maintenance inventory and retained third-party notices. The complete upstream source archive/tree includes its pinned submodules and original fixtures.

## Release review and promotion procedure

1. Resolve or explicitly accept the documented limitations. Run the official SDKcraft/Spread jobs on a supported runner with KVM if this VPS cannot execute them; do not turn an unexecuted job into a pass.
2. Review the actual final SDK artifact and its SHA256, the source diff, provider results, persistent-state behavior and any required external service configuration. Check the bundled third-party license/notice and browser terms before distribution.
3. Obtain explicit approval before pushing this branch or uploading the SDK. Preserve the `hermes-rea` Store identity and use the exact reviewed artifact, rather than substituting an untested rebuild.
4. If upload is approved, upload that artifact to `latest/edge` with `sdkcraft upload <reviewed-artifact.sdk> --release latest/edge`, then record the returned revision and checksum. No revision number is assumed in advance.
5. Install that Store revision into a new Workshop and repeat the relevant operational checks. Separately verify Hermes A's pinned plugin/client against C's upgraded CLI/MCP catalog and restricted SSH transport, including worker failure without local execution fallback. C-only testing does not establish complete A/B/C routing or independent audit.
6. Promote the same tested revision only after the corresponding release approval and acceptance checks. Do not rebuild between testing a revision and promoting it.

The local artifact name is `hermes-rea_amd64_ubuntu@26.04.sdk`. Its final location, SHA256 and actual build/install outcomes must come from the completed validation record; this procedure is not itself evidence that those checks passed.
