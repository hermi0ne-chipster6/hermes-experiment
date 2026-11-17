// Regenerate inert fixtures from the exact upstream REA source, never a newer HEAD.
// Usage: node regenerate-firmware-format-fixtures.mjs SOURCE_ROOT BUILT_RUNTIME_ROOT
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, dirname, relative } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { stripTypeScriptTypes, createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
const commit = '51459cf203ae1eb6b586a95b21899eaa0f631823';
if (process.argv.length !== 4) throw new Error('Supply pinned source and built runtime roots');
const [source, runtime] = process.argv.slice(2).map(x => resolve(x));
if (execFileSync('git', ['-C', source, 'rev-parse', 'HEAD'], {encoding:'utf8'}).trim() !== commit)
  throw new Error('Refuse a source baseline other than ' + commit);
function readPinned(name) {
  const bytes = readFileSync(resolve(source, name));
  const committed = execFileSync('git', ['-C', source, 'show', `${commit}:${name}`]);
  if (!bytes.equals(committed)) throw new Error('Refuse modified pinned input ' + name);
  return bytes;
}
const require = createRequire(resolve(runtime, 'package.json'));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const lockBytes = readPinned('package-lock.json');
const wantedProtobuf = JSON.parse(lockBytes).packages['node_modules/@bufbuild/protobuf'].version;
const wirePath = require.resolve('@bufbuild/protobuf/wire');
let protobufRoot = dirname(wirePath);
let protobufPackage;
for (;;) {
  const packagePath = resolve(protobufRoot, 'package.json');
  if (existsSync(packagePath)) {
    const value = JSON.parse(readFileSync(packagePath, 'utf8'));
    if (value.name === '@bufbuild/protobuf') { protobufPackage = value; break; }
  }
  const parent = dirname(protobufRoot);
  if (parent === protobufRoot) throw new Error('Cannot locate protobuf package metadata');
  protobufRoot = parent;
}
if (protobufPackage.version !== wantedProtobuf)
  throw new Error('Protobuf dependency does not match pinned upstream lock');
const generatorInputs = {node:process.versions.node, upstream_lock_sha256:sha(lockBytes),
  protobuf_version:protobufPackage.version, protobuf_wire_sha256:sha(readFileSync(wirePath))};
const sources = {};
const modules = new Map();
async function load(name) {
  const absolute = resolve(source, name);
  if (modules.has(absolute)) return modules.get(absolute);
  const bytes = readPinned(name);
  sources[name] = sha(bytes);
  let text = stripTypeScriptTypes(bytes.toString(), {mode:'transform'});
  for (const match of [...text.matchAll(/from\s+(['"])([^'"]+)\1/g)]) {
    const spec = match[2];
    if (spec.startsWith('node:')) continue;
    let target;
    if (spec.startsWith('.')) {
      const path = resolve(dirname(absolute), spec);
      const ts = path.replace(/\.js$/, '.ts');
      if (existsSync(ts)) {
        const nested = await load(relative(source, ts));
        target = nested.url;
      } else {
        const rel = relative(resolve(source, 'src'), path);
        if (rel.startsWith('..')) throw new Error('Unexpected runtime import ' + spec);
        target = pathToFileURL(resolve(runtime, 'dist', rel)).href;
      }
    } else target = pathToFileURL(require.resolve(spec)).href;
    text = text.replace(match[0], `from ${JSON.stringify(target)}`);
  }
  const url = 'data:text/javascript;base64,' + Buffer.from(text).toString('base64');
  const value = {url, exports:await import(url)};
  modules.set(absolute, value);
  return value;
}
const factory = async p => (await load(p)).exports;
const payload = Buffer.from('HERMES_FORMAT_PAYLOAD_01\n');
const fixtures = {};
function add(format, filename, bytes, members, note='') {
  fixtures[format] = {filename, sha256:sha(bytes), bytes:bytes.length,
    base64:Buffer.from(bytes).toString('base64'),
    expected_members:Object.fromEntries(Object.entries(members).map(([path,data]) =>
      [path,{sha256:sha(data), bytes:data.length}])), note};
}
const region = (start,length) => `0x${start.toString(16).padStart(8,'0')}-0x${(start+length-1).toString(16).padStart(8,'0')}.bin`;
const {buildUImage} = await factory('tests/fixtures/uimage.ts');
add('uimage','hermes.uimage',buildUImage({payload}),{'payload.bin':payload});
const {fitFixture} = await factory('src/artifacts/fit/FitImage.fixture.ts');
const {dtString} = await factory('src/domain/firmware/devicetree.fixture.ts');
add('fit','hermes.itb',fitFixture({images:[{name:'hermes',data:payload,hashes:['sha256'],properties:{type:dtString('firmware'),arch:dtString('arm'),os:dtString('linux'),compression:dtString('none')}}]}),{'images/hermes.bin':payload});
const {intelHexRecord,srecRecord} = await factory('src/domain/firmware/hexRecords.fixture.ts');
add('intel-hex','hermes.hex',Buffer.from(intelHexRecord(0,0x1000,[...payload])+'\n'+intelHexRecord(1,0)+'\n'),{[region(0x1000,payload.length)]:payload});
add('srec','hermes.s19',Buffer.from(srecRecord(1,0x1000,[...payload])+'\n'+srecRecord(9,0x1000)+'\n'),{[region(0x1000,payload.length)]:payload});
const esp = await factory('tests/fixtures/espImage.ts');
add('esp-image','hermes.esp.bin',esp.espImage({segments:esp.ESP32C3_APP_SEGMENTS}),Object.fromEntries(esp.ESP32C3_APP_SEGMENTS.map((segment,index)=>[`segment-${String(index).padStart(2,'0')}.bin`,segment.data])), 'Canonical synthetic ESP32-C3 application descriptor and four inert segment payloads.');
const uf2 = await factory('src/domain/firmware/uf2.fixture.ts');
const uf2payload = Buffer.from(uf2.patternBytes(512,37));
add('uf2','hermes.uf2',uf2.uf2File(uf2.uf2Image(uf2.RP2040_FAMILY,0x10000000,uf2payload)),{['family-0xe48bff56/'+region(0x10000000,512)]:uf2payload});
const {dfuseFile} = await factory('src/domain/firmware/dfuse.fixture.ts');
add('dfuse','hermes.dfu',dfuseFile({targets:[{alternateSetting:0,name:'Hermes fixture',elements:[{address:0x08000000,data:payload}]}]}),{['target-0/element-0-'+region(0x08000000,payload.length)]:payload});
const flash = await factory('src/domain/firmware/espFlash.fixture.ts');
const flashbytes = flash.espFlashDump({size:0x11000,bootloader:{at:0,bytes:esp.espImage({segments:esp.ESP32C3_BOOTLOADER_SEGMENTS})},table:flash.partitionTable([{type:1,subtype:2,offset:0x10000,size:0x1000,label:'fixture',flags:0}]),parts:[{at:0x10000,bytes:payload}]});
add('esp-flash-image','hermes.flash.bin',flashbytes,{'bootloader.bin':flashbytes.subarray(0,0x8000),'partition-table.bin':flashbytes.subarray(0x8000,0x9000),'partitions/fixture.bin':flashbytes.subarray(0x10000,0x11000)},'Offline whole-flash region recovery; no device, decryption or boot execution.');
const {buildBootImage} = await factory('tests/fixtures/androidBootImage.ts');
const ramdisk = Buffer.from('HERMES_RAMDISK_FIXTURE\n');
add('android-boot-image','hermes.boot.img',buildBootImage({version:3,kernel:payload,ramdisk}),{kernel:payload,ramdisk});
const {buildAndroidOtaPayload} = await factory('src/domain/firmware/androidOtaPayload.fixture.ts');
const partition = Buffer.alloc(4096); payload.copy(partition);
add('android-ota-payload','hermes.payload.bin',buildAndroidOtaPayload({partitions:[{name:'boot',newSize:4096,operations:[{type:0,data:partition,dstExtents:[{startBlock:0,numBlocks:1}]}]}]}),{'boot.img':partition},'Full REPLACE operation only; no delta application or signature authentication claim.');
const {inesFixture} = await factory('tests/fixtures/ines.ts');
const ines = inesFixture();
add('ines','hermes.nes',ines,{'header.bin':ines.subarray(0,16),'prg/000.bin':Buffer.alloc(16384,0x41),'prg/001.bin':Buffer.alloc(16384,0x42),'chr/000.bin':Buffer.alloc(8192,0x43)},'Upstream synthetic test bytes, not a game ROM; no emulator or mapper execution.');
const {buildGodotPck1} = await factory('tests/fixtures/godotPck.ts');
add('godot-pck','hermes.pck',buildGodotPck1([{path:'res://fixture.txt',data:payload}]),{'fixture.txt':payload},'Plain Godot PCK v1, MD5-protected member; not encrypted PCK.');
const {buildUnityFs} = await factory('tests/fixtures/unityfs.ts');
add('unityfs','hermes.unity3d',buildUnityFs([{path:'fixture.txt',data:payload}],{blockCompression:2,blocksInfoCompression:2}),{'fixture.txt':payload},'Synthetic LZ4 literal-compressed blocks and directory; not arbitrary Unity serialized object interpretation.');
const {buildWxapkg} = await factory('tests/fixtures/wxapkg.ts');
add('wxapkg','hermes.wxapkg',buildWxapkg([{path:'/fixture.txt',data:payload}]),{'fixture.txt':payload},'Plain package only; encrypted PC-client packages remain upstream-limited.');
const output = {schema_version:1,upstream_commit:commit,provenance:'Inert fixture factories from morluto/rea; original factory bytes are hashed below. Payload/member oracles are independently supplied here, not generated by a reader under test.',license:readPinned('LICENSE').toString('utf8'),generator_inputs:generatorInputs,source_sha256:sources,fixtures};
writeFileSync(new URL('firmware-format-fixtures.json',import.meta.url),JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({formats:Object.keys(fixtures),sources:Object.keys(sources).length,fixture_bytes:Object.values(fixtures).reduce((n,x)=>n+x.bytes,0)}));
