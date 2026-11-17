#!/usr/bin/env node
// Diagnostic only: real installed Frida + Node child_process, without REA MCP.
// Use the existing source-owned frida-fixture (main sleeps two seconds then exits).
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  assert(process.argv[i].startsWith('--') && process.argv[i + 1], 'Expected --name value pairs');
  args[process.argv[i].slice(2)] = process.argv[i + 1];
}
if (!args.output || !args.fixture) {
  process.stderr.write('Usage: node frida_process_probe.mjs --output NEW-DIR --fixture OWNED-TWO-SECOND-ELF [--package-root /var/lib/workshop/sdk/hermes-rea/rea/node_modules/rea-agents] [--mode import|enumerate|injection]\n');
  process.exit(2);
}
assert(process.getuid() !== 0, 'Run as the unprivileged rea account');
const output = resolve(args.output), fixture = resolve(args.fixture);
mkdirSync(output, { recursive: false, mode: 0o700 });
const mode = args.mode ?? 'injection';
assert(['import', 'enumerate', 'injection'].includes(mode));
const root = resolve(args['package-root'] ?? '/var/lib/workshop/sdk/hermes-rea/rea/node_modules/rea-agents');
const require = createRequire(join(root, 'package.json'));
const rows = [];
let device, session, script, pid, targetIdentity, sentinel, resumed = false;
const started = Date.now();
const status = (selectedPid = 'self') => {
  try {
    return Object.fromEntries(readFileSync(`/proc/${selectedPid}/status`, 'utf8').split('\n')
      .filter(line => /^(Name|State|Pid|PPid|Threads|SigPnd|ShdPnd|SigBlk|SigIgn|SigCgt):/.test(line))
      .map(line => { const at = line.indexOf(':'); return [line.slice(0, at), line.slice(at + 1).trim()]; }));
  } catch (error) { return { unavailable: error.code }; }
};
// /proc/PID/stat field 22 identifies this owned process across PID reuse. The
// command field may itself contain spaces or parentheses, so split after its
// final closing parenthesis rather than splitting the whole record.
function readTargetIdentity(targetPid) {
  try {
    const stat = readFileSync(`/proc/${targetPid}/stat`, 'utf8');
    const fields = stat.slice(stat.lastIndexOf(')') + 2).trim().split(/\s+/);
    assert(fields.length >= 20 && /^\d+$/.test(fields[19]), 'Malformed owned target /proc stat');
    return { pid: targetPid, starttime: fields[19], state: fields[0] };
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}
async function observeOwnedTargetExit(identity, timeoutMs = 10000) {
  const until = Date.now() + timeoutMs;
  for (;;) {
    const current = readTargetIdentity(identity.pid);
    if (current === null) return { observation: 'proc-entry-gone', ...identity };
    assert(current.starttime === identity.starttime, 'Owned target PID was reused before exit observation');
    if (current.state === 'Z' || current.state === 'X') {
      return { observation: 'exited-process-state', ...current };
    }
    assert(Date.now() < until, `Owned Frida target did not exit within ${timeoutMs}ms`);
    await new Promise(resolvePoll => setTimeout(resolvePoll, 50));
  }
}
const record = (row) => {
  rows.push({ ...row, elapsed_ms: Date.now() - started, node_signal_state: status() });
  writeFileSync(join(output, 'results.json'), JSON.stringify(rows, null, 2) + '\n');
  process.stdout.write(JSON.stringify(rows.at(-1)) + '\n');
};
const deadline = (promise, label, milliseconds = 15000) => {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} exceeded ${milliseconds}ms`)), milliseconds);
  })]).finally(() => clearTimeout(timer));
};
const probe = async stage => {
  for (const [kind, command, argv, expected] of [
    ['ps', '/usr/bin/ps', ['-p', String(process.pid), '-o', 'pid=,ppid=,stat='], String(process.pid)],
    ['node-child', process.execPath, ['-e', 'process.stdout.write("owned-child-ok")'], 'owned-child-ok'],
  ]) {
    await new Promise(resolveProbe => {
      let child, timer, stdout = '', stderr = '', finished = false;
      const events = [];
      const done = (ok, detail) => {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        record({ stage, kind, status: ok ? 'pass' : 'fail', child_pid: child?.pid,
                 child_state: child?.pid ? status(child.pid) : null, events, stdout, stderr, ...detail });
        resolveProbe();
      };
      child = spawn(command, argv, { stdio: ['ignore', 'pipe', 'pipe'] });
      child.stdout.on('data', data => { stdout = (stdout + data).slice(0, 4096); });
      child.stderr.on('data', data => { stderr = (stderr + data).slice(0, 4096); });
      child.on('spawn', () => events.push('spawn'));
      child.on('exit', (code, signal) => events.push({ exit: code, signal }));
      child.on('error', error => done(false, { error: error.message }));
      child.on('close', (code, signal) => done(code === 0 && stdout.includes(expected), { exit_code: code, signal }));
      timer = setTimeout(() => {
        done(false, { timeout_ms: 4000, exit_code: child.exitCode });
        // Only signal this ChildProcess handle if it is still live, never a zombie.
        if (!status(child.pid).State?.startsWith('Z')) child.kill('SIGKILL');
      }, 4000);
    });
  }
};
const step = async (label, fn) => {
  const value = await deadline(fn(), label);
  record({ stage: label, status: 'pass', ...(label === 'frida-spawn-owned-fixture' ? { target_identity: targetIdentity } : {}) });
  await probe(label);
  return value;
};
const overall = setTimeout(() => {
  record({ stage: 'overall-deadline', status: 'fail', reason: '150-second diagnostic budget expired' });
  // The fixture is owned and finite. Resume it before terminating the diagnostic.
  if (device && pid && !resumed) void device.resume(pid).catch(() => {});
  if (sentinel && !status(sentinel.pid).State?.startsWith('Z')) sentinel.kill('SIGKILL');
  setTimeout(() => process.exit(1), 2000);
}, 150000);
try {
  record({ stage: 'identity', status: 'pass', exec_path: process.execPath, versions: process.versions,
           package_root: root, fixture, fixture_sha256: createHash('sha256').update(readFileSync(fixture)).digest('hex'), mode });
  // Keep libuv's child watcher active across the Frida target's exit. With no
  // other children, a later spawn may reinstall SIGCHLD and mask frida-node#121.
  sentinel = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore' });
  await deadline(new Promise((resolveSentinel, rejectSentinel) => {
    sentinel.once('spawn', resolveSentinel);
    sentinel.once('error', rejectSentinel);
  }), 'owned-node-sentinel-start');
  record({ stage: 'owned-node-sentinel-start', status: 'pass', child_pid: sentinel.pid });
  await probe('before-frida-import');
  const module = await step('frida-import', () => import(pathToFileURL(require.resolve('frida')).href));
  const frida = module.getDeviceManager ? module : module.default;
  if (mode !== 'import') {
    const manager = await step('frida-device-manager', async () => frida.getDeviceManager());
    const devices = await step('frida-enumerate-devices', () => manager.enumerateDevices());
    device = devices.find(item => item.id === 'local');
    assert(device, 'Local Frida device unavailable');
    await step('frida-enumerate-processes', async () => {
      const processes = await device.enumerateProcesses();
      assert(processes.some(item => item.pid === process.pid), 'Frida cannot enumerate probe PID');
    });
    if (mode === 'injection') {
      pid = await step('frida-spawn-owned-fixture', async () => {
        const spawnedPid = await device.spawn(fixture);
        pid = spawnedPid;
        targetIdentity = readTargetIdentity(spawnedPid);
        assert(targetIdentity, 'Owned suspended Frida target disappeared before identity capture');
        return spawnedPid;
      });
      session = await step('frida-attach-owned-fixture', () => device.attach(pid));
      const messages = [];
      await step('frida-load-script', async () => {
        script = await session.createScript('send({fixture:"owned-frida-child-probe",pid:Process.id});');
        script.message.connect(message => messages.push(message));
        await script.load();
        assert(messages.some(item => item.type === 'send' && item.payload?.pid === pid), 'Injected script did not report owned PID');
      });
      await step('frida-unload-script', async () => { await script.unload(); script = undefined; });
      await step('frida-resume-owned-fixture', async () => { await device.resume(pid); resumed = true; });
      await step('frida-detach-owned-fixture', async () => { if (!session.isDetached()) await session.detach(); session = undefined; });
      const targetExit = await observeOwnedTargetExit(targetIdentity);
      record({ stage: 'owned-frida-target-exit', status: 'pass', ...targetExit });
      await probe('after-owned-fixture-exit');
    }
  }
} catch (error) {
  record({ stage: 'diagnostic-error', status: 'fail', reason: error.stack });
} finally {
  for (const [label, action] of [
    ['cleanup-script', () => script?.unload()],
    ['cleanup-session', () => session && !session.isDetached() ? session.detach() : undefined],
    ['cleanup-resume', () => device && pid && !resumed ? device.resume(pid) : undefined],
  ]) {
    try { await deadline(Promise.resolve().then(action), label, 5000); }
    catch (error) { record({ stage: label, status: 'fail', reason: error.message }); }
  }
  if (sentinel) {
    await new Promise(resolveSentinel => {
      const timer = setTimeout(() => {
        record({ stage: 'owned-node-sentinel-cleanup', status: 'fail', child_state: status(sentinel.pid),
                 reason: 'Owned Node sentinel received SIGKILL but emitted no exit within 2s' });
        resolveSentinel();
      }, 2000);
      sentinel.once('exit', () => {
        clearTimeout(timer);
        record({ stage: 'owned-node-sentinel-cleanup', status: 'pass' });
        resolveSentinel();
      });
      if (!status(sentinel.pid).State?.startsWith('Z')) sentinel.kill('SIGKILL');
    });
  }
  clearTimeout(overall);
  writeFileSync(join(output, 'final.json'), JSON.stringify({ completed: true,
    failed_checks: rows.filter(row => row.status === 'fail').length, duration_ms: Date.now() - started }, null, 2) + '\n');
}
// An unreaped ChildProcess handle is exactly the defect under observation.
// Exit explicitly after retaining events; do not turn that handle into an endless probe.
process.exit(rows.some(row => row.status === 'fail') ? 1 : 0);
