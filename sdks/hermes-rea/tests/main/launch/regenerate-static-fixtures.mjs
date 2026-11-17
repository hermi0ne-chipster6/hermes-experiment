// Usage: node regenerate-static-fixtures.mjs /path/to/pinned/rea /path/to/built/rea-agents
// Requires Node 24 with TypeScript stripping; does not execute fixture payloads.
import { readFileSync, writeFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";

const [sourceRoot, runtimeRoot] = process.argv.slice(2).map((path) => resolve(path));
if (!sourceRoot || !runtimeRoot) throw new Error("Supply pinned upstream source and built runtime roots");
const commit = "51459cf203ae1eb6b586a95b21899eaa0f631823";
if (execFileSync("git", ["-C", sourceRoot, "rev-parse", "HEAD"], { encoding: "utf8" }).trim() !== commit)
  throw new Error("Fixture source must match pinned upstream commit " + commit);
const load = (path) => import(pathToFileURL(resolve(sourceRoot, path)).href);
const { createIl2cppMetadataFixture } = await load("tests/fixtures/il2cpp/metadata.ts");
const { aotFixtureImage } = await load("src/flutter/FlutterBuild.fixture.ts");
const { peImportImage } = await load("tests/fixtures/binaryDiagnostics/peImports.ts");
const { peCertificateFixture } = await load("src/native/pe/PeCertificates.fixture.ts");
const { peResourceFixture } = await load("src/domain/pe/peResources.fixture.ts");
const { buildManagedPeFixture } = await load("scripts/fixtures/managed/pe.mjs");
// This upstream fixture uses the shared public field-layout catalog. Resolve
// its one runtime import to the build of the same pinned source, not a mock.
const loadConfigSource = stripTypeScriptTypes(readFileSync(resolve(sourceRoot,
  "src/native/pe/PeLoadConfig.fixture.ts"), "utf8")).replace(
    "../../domain/native/peLoadConfig.js",
    pathToFileURL(resolve(runtimeRoot, "dist/domain/native/peLoadConfig.js")).href);
const { peLoadConfigImage } = await import("data:text/javascript;base64," + Buffer.from(loadConfigSource).toString("base64"));
const encode = (bytes) => Buffer.from(bytes).toString("base64");
const fixtures = {
  provenance: "Generated from morluto/rea commit " + commit + "; MIT, copyright 2026 morluto. See static-fixtures-LICENSE.txt and regenerate-static-fixtures.mjs. Inert synthetic format fixtures; no executable application.",
  il2cpp: encode(createIl2cppMetadataFixture({ version: 29 }).bytes),
  flutter: encode(aotFixtureImage()),
  pe_imports: encode(peImportImage()),
  pe_certificates: encode(peCertificateFixture()),
  pe_resources: encode(peResourceFixture().bytes),
  pe_load_config: encode(peLoadConfigImage()),
  managed: encode(buildManagedPeFixture({ typeName: "HermesWorkflow", typeNamespace: "Hermes", methodName: "Greet" })),
};
writeFileSync(new URL("static-fixtures.json", import.meta.url), JSON.stringify(fixtures, null, 2) + "\n");
writeFileSync(new URL("static-fixtures-LICENSE.txt", import.meta.url), readFileSync(resolve(sourceRoot, "LICENSE")));
