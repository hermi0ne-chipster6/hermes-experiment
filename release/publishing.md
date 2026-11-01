# Publish the registered Hermes SDKs

**Published 2026-11-01:** `hermes-experiment` 0.22.5, `hermes-execution` 1.2.0 and `hermes-rea` 6.7.0 are each revision **1** on **`latest/edge`**, under `codyprevost`. See the [publication record](../reports/publishing/publication.md). The commands below describe the procedure for future reviewed builds; initial publication is already complete. Inspect existing revisions before repeating an upload.

The operator reports registering `hermes-experiment`, `hermes-execution` and `hermes-rea`. Workshop A's SDK name is now `hermes-experiment`; the official upstream remains NousResearch Hermes Agent. The former `hermes-agent` SDK archive and earlier source ZIP are superseded and must not be uploaded.

Use the built `.sdk` artifacts, not the source ZIP. From the deliverable root, verify the current checksums before uploading:

```bash
sha256sum -c reports/SHA256SUMS
sdkcraft login
sdkcraft whoami
```

The following commands write to the live SDK Store. Start on edge; promotion is separate and remains under operator review:

```bash
sdkcraft upload sdks/hermes-experiment/hermes-experiment_amd64_ubuntu@26.04.sdk --release latest/edge
sdkcraft upload sdks/hermes-execution/hermes-execution_amd64_ubuntu@26.04.sdk --release latest/edge
sdkcraft upload sdks/hermes-rea/hermes-rea_amd64_ubuntu@26.04.sdk --release latest/edge
```

Record each revision number from the upload output. Test definitions consuming those Store revisions on `latest/edge`, then promote the exact tested revision with `sdkcraft release SDK_NAME REVISION latest/stable`, substituting the appropriate name and actual revision number. Do not rebuild between testing and promotion. Complete the outstanding checks in the verification report before claiming stable production readiness.

Local development uses `try-hermes-experiment` for A. Store definitions use `hermes-experiment`; interface references and secret identifiers always use the bare name, for example `hermes-experiment:diary` and `hermes-experiment.model-key`.

A rename creates a different SDK identity. On an existing deployment, old mount sources and secret/tunnel connections do not automatically become the new SDK's connections. Preserve existing state and explicitly reconnect/remount before activation. This project targets a fresh VPS; no production mounts or credentials were migrated during the rename.

The source folder is `sdks/hermes-experiment/`. The local validation project remains `validation/hermes-agent/` to retain its existing Workshop project identity and historical evidence.
