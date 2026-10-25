import { spawn } from 'node:child_process';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const url = process.argv[2] || 'http://127.0.0.1:8766/';
const chromePath = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const profile = await mkdtemp(join(tmpdir(), 'workcation-cdp-'));
const port = 9336;
const chrome = spawn(chromePath, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, '--window-size=375,800', url,
], { stdio: 'ignore' });

const pause = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 60; i++) {
  try {
    const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
    target = pages.find(p => p.type === 'page');
    if (target) break;
  } catch {}
  await pause(100);
}
if (!target) throw new Error('Chrome CDP target not available');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let seq = 0;
const pending = new Map();
ws.onmessage = event => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const call = (method, params = {}) => new Promise(resolve => {
  const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params }));
});
await call('Emulation.setDeviceMetricsOverride', { width: 320, height: 800, deviceScaleFactor: 1, mobile: true });
await call('Page.reload');
await pause(1200);
const evaluate = async expression => (await call('Runtime.evaluate', { expression, returnByValue: true })).result.result.value;
const base = await evaluate(`(() => ({
  title: document.title,
  cards: document.querySelectorAll('[data-testid="deal-card"]').length,
  visas: document.querySelectorAll('[data-testid="visa-rule"]').length,
  visible: [...document.querySelectorAll('[data-testid="deal-card"]')].filter(x => !x.hidden).length,
  overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  minTarget: Math.min(...[...document.querySelectorAll('select,input,summary,a')].map(x => Math.min(x.getBoundingClientRect().width,x.getBoundingClientRect().height)).filter(Boolean))
}))()`);
await evaluate(`(() => { document.querySelector('#room').value='private'; document.querySelector('#room').dispatchEvent(new Event('input',{bubbles:true})); return true; })()`);
const filtered = await evaluate(`(() => ({visible:[...document.querySelectorAll('[data-testid="deal-card"]')].filter(x=>!x.hidden).length, rooms:[...document.querySelectorAll('[data-testid="deal-card"]')].filter(x=>!x.hidden).map(x=>x.dataset.room), text:document.querySelector('#resultText').textContent}))()`);
console.log(JSON.stringify({ base, filtered }));
if (base.title !== 'Warm Workcation Tracker' || base.cards < 1 || base.visas !== base.cards || base.overflow || filtered.visible < 1 || filtered.rooms.some(r => r !== 'private')) process.exitCode = 1;
ws.close(); chrome.kill();
