// Usage: node regenerate-container-format-fixtures.mjs PINNED-REA BUILT-REA
// Source-owned inert fixtures; no generated carrier or embedded script is run.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { stripTypeScriptTypes } from 'node:module';
import { resolve, dirname, relative } from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';
const args = process.argv.slice(2);
if (args.length !== 2) throw new Error('Supply pinned source and built REA roots');
const [sourceRoot, runtimeRoot] = args.map(value => resolve(value));
const commit = '51459cf203ae1eb6b586a95b21899eaa0f631823';
if (execFileSync('git', ['-C', sourceRoot, 'rev-parse', 'HEAD'], {encoding:'utf8'}).trim() !== commit)
  throw new Error('Source does not match pinned upstream');
if (readFileSync(resolve(runtimeRoot, '../../UPSTREAM_COMMIT'), 'utf8').trim() !== commit)
  throw new Error('Runtime must be the SDK build of the pinned upstream commit');
const hashes = {}, urls = new Map();
function sourceUrl(path) {
  if (urls.has(path)) return urls.get(path);
  const bytes = readFileSync(path);
  hashes[relative(sourceRoot, path)] = createHash('sha256').update(bytes).digest('hex');
  let code = stripTypeScriptTypes(bytes.toString('utf8'));
  code = code.replace(/from\s+(["'])(\.[^"']+)\1/g, (all, quote, specifier) => {
    const child = resolve(dirname(path), specifier.replace(/\.js$/, '.ts'));
    // Fixture helpers use source-owned fixture imports. Bun's one real runtime
    // layout import resolves to the build of exactly this pinned REA source.
    const url = /(?:\.fixture|\/fixtures\/)/.test(child) && existsSync(child)
      ? sourceUrl(child)
      : pathToFileURL(resolve(runtimeRoot, 'dist', relative(resolve(sourceRoot, 'src'), child).replace(/\.ts$/, '.js'))).href;
    return `from ${quote}${url}${quote}`;
  });
  const url = 'data:text/javascript;base64,' + Buffer.from(code).toString('base64');
  urls.set(path, url);
  return url;
}
const load = path => import(sourceUrl(resolve(sourceRoot, path)));
const {dotnetBundleFixture} = await load('src/artifacts/dotnet/DotnetBundle.fixture.ts');
const {bunModuleGraphPayload, elfAppendedBunPayload} = await load('src/artifacts/bun/BunStandalone.fixture.ts');
const {buildDenoSection, denoElf} = await load('src/artifacts/deno/DenoStandalone.fixture.ts');
const {nodeSeaElf} = await load('src/artifacts/nodeSea/NodeSea.fixture.ts');
const {cArchiveExecutable} = await load('src/artifacts/pyinstaller/CArchive.fixture.ts');
const {asarHeaderBytes} = await load('tests/fixtures/asarHeader.ts');
const marker = Buffer.from('hermes-container-fixture\n');
const script = Buffer.from('throw new Error("hermes fixture must not execute");\n');
const encode = value => Buffer.from(value).toString('base64');
const item = (bytes, format, members) => ({format, bytes_base64:encode(bytes), sha256:createHash('sha256').update(bytes).digest('hex'), members:Object.fromEntries(Object.entries(members).map(([path, data]) => [path, encode(data)]))});
const fixtures = {
  asar: item(Buffer.concat([asarHeaderBytes(JSON.stringify({files:{'main.js':{size:script.length,offset:'0'}}})),script]), 'asar', {'main.js':script}),
  'dotnet-bundle': item(dotnetBundleFixture([{path:'data/marker.txt',bytes:marker,fileType:0},{path:'data/compressed.txt',bytes:marker,compressed:true,fileType:0}]).bytes, 'dotnet-bundle', {'data/marker.txt':marker,'data/compressed.txt':marker}),
  'bun-standalone': item(elfAppendedBunPayload(bunModuleGraphPayload({modules:[{name:'/$bunfs/root/main.js',contents:script}]})), 'bun-standalone', {'$bunfs/root/main.js':script}),
  'deno-standalone': item(denoElf(buildDenoSection({vfsFileData:script,vfs:[{File:{n:'main.ts',o:[0,script.length],u:true}}]})), 'deno-standalone', {'main.ts':script}),
  'node-sea': item(nodeSeaElf({codePath:'main.js',main:script,fuse:'unset',assets:[{name:'data/marker.txt',body:marker}]}), 'node-sea', {'main.js':script,'data/marker.txt':marker}),
  pyinstaller: item(cArchiveExecutable({layout:'2.1',pythonVersion:310,pythonLibrary:'libpython3.10.so',members:[{name:'data/marker.txt',typeCode:'x',payload:marker,compress:true}]}), 'pyinstaller', {'data/marker.txt':marker}),
};
const output = {provenance:{repository:'https://github.com/morluto/rea',commit,license:'MIT; copyright2026 morluto; see static-fixtures-LICENSE.txt',generator:'regenerate-container-format-fixtures.mjs',source_sha256:hashes,payload_execution:false},fixtures};
writeFileSync(new URL('container-format-fixtures.json',import.meta.url),JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({fixtures:Object.keys(fixtures),source_files:Object.keys(hashes).length,payload_execution:false}));
