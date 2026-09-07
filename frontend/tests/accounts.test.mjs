import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const task = { id: 'homework', kind: 'flexible', title: 'Math', duration_min: 60, days: [0] };
const response = (status, data) => ({ status, ok: status < 400, json: async () => data });
const tick = () => new Promise(resolve => setImmediate(resolve));

function harness() {
  const elements = new Map();
  function element() {
    return {
      value: '', textContent: '', hidden: false, disabled: false, dataset: {}, style: {},
      children: [], listeners: {},
      addEventListener(name, handler) { this.listeners[name] = handler; },
      appendChild(child) { this.children.push(child); },
      replaceChildren() { this.children = []; },
      querySelectorAll() { return []; }, reset() {}, focus() {}, click() {},
    };
  }
  for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], element());
  const local = new Map();
  let handler = async () => response(401, { detail: 'Please sign in' });
  const requests = [];
  const context = vm.createContext({
    document: {
      getElementById: id => { assert.ok(elements.has(id), `Missing HTML element ${id}`); return elements.get(id); },
      documentElement: { dataset: { theme: 'nocturne' } },
      createElement: element, addEventListener() {},
    },
    window: { addEventListener() {} },
    localStorage: { getItem: key => local.get(key), removeItem: key => local.delete(key) },
    fetch: async (path, options) => { requests.push({ path, options }); return handler(path, options); },
    getComputedStyle: () => ({ getPropertyValue: () => '2.75rem' }),
    setTimeout, clearTimeout, AbortController, structuredClone, console,
    confirm: () => true,
  });
  vm.runInContext(source, context);
  return {
    elements, local, requests,
    run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    async login(id = 1, blocks = []) {
      await tick();
      handler = async path => response(200, path === '/api/week' ? { blocks, revision: 0 } : { theme: 'nocturne' });
      await vm.runInContext(`loadAccount({id:${id},username:'student${id}'})`, context);
    },
  };
}

test('boot requires sign-in and never fetches a demo or exposes legacy data', async () => {
  const h = harness();
  h.local.set('flexweek.week.v1', JSON.stringify({ blocks: [task] }));
  await tick();
  assert.equal(h.elements.get('planner').hidden, true);
  assert.equal(h.run('currentBlocks.length'), 0);
  assert.deepEqual(h.requests.map(r => r.path), ['/api/auth/me']);
});

test('failed save retains the draft and a retry commits the same week', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.handle(async () => { throw new Error('Offline'); });
  assert.equal(await h.run('saveWeek()'), false);
  assert.equal(h.run('dirty'), true);
  assert.equal(h.run('currentBlocks[0].title'), 'Math');
  assert.match(h.elements.get('status').textContent, /Not saved/);
  h.handle(async (_path, options) => {
    assert.equal(options.headers['X-FlexWeek-Account'], '1');
    const payload = JSON.parse(options.body);
    assert.equal(payload.blocks[0].title, 'Math');
    assert.equal(payload.revision, 0);
    return response(200, { revision: 1 });
  });
  assert.equal(await h.run('saveWeek()'), true);
  assert.equal(h.run('dirty'), false);
  assert.equal(h.run('revision'), 1);
});

test('revision conflict preserves edits and prevents blind retry', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.handle(async () => response(409, { detail: 'Week changed' }));
  await h.run('saveWeek()');
  const count = h.requests.length;
  await h.run('saveWeek()');
  assert.equal(h.requests.length, count);
  assert.equal(h.run('dirty'), true);
  assert.equal(h.elements.get('retry-save').disabled, true);
  assert.equal(h.run('currentBlocks[0].title'), 'Math');
});

test('expired session hides private data and restores unsaved edits only to the same account', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.handle(async () => response(401, { detail: 'Session expired' }));
  await h.run('saveWeek()');
  assert.equal(h.elements.get('planner').hidden, true);
  assert.equal(h.elements.get('week').children.length, 0);
  assert.equal(h.run('currentBlocks.length'), 0);
  await h.login(1);
  assert.equal(h.run('currentBlocks[0].title'), 'Math');
  assert.equal(h.run('dirty'), true);
  h.run('signedOut()');
  await h.login(2);
  assert.equal(h.run('currentBlocks.length'), 0);
  assert.equal(h.run('dirty'), false);
});

test('late save response cannot repopulate a signed-out screen', async () => {
  const h = harness();
  await h.login(1, [task]);
  let resolve;
  h.handle(() => new Promise(done => { resolve = done; }));
  const pending = h.run('saveWeek()');
  h.run('signedOut()');
  resolve(response(200, { revision: 1 }));
  await pending;
  assert.equal(h.run('account'), null);
  assert.equal(h.run('currentBlocks.length'), 0);
  assert.equal(h.elements.get('planner').hidden, true);
});

test('invalid browser import leaves the existing week intact', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.local.set('flexweek.week.v1', '{broken');
  const count = h.requests.length;
  await h.elements.get('import-week').listeners.click();
  assert.equal(h.run('currentBlocks[0].title'), 'Math');
  assert.equal(h.requests.length, count);
  assert.equal(h.local.get('flexweek.week.v1'), '{broken');
  assert.match(h.elements.get('import-status').textContent, /invalid/);
});

test('successful explicit legacy import saves to the account and removes the legacy copy', async () => {
  const h = harness();
  await h.login();
  h.local.set('flexweek.week.v1', JSON.stringify({ blocks: [task] }));
  h.handle(async (_path, options) => {
    assert.equal(JSON.parse(options.body).blocks[0].title, 'Math');
    return response(200, { revision: 1 });
  });
  await h.elements.get('import-week').listeners.click();
  assert.equal(h.local.has('flexweek.week.v1'), false);
  assert.equal(h.run('dirty'), false);
});

test('failed theme save reverts the displayed theme', async () => {
  const h = harness();
  await h.login();
  h.handle(async () => response(503, { detail: 'Unavailable' }));
  h.elements.get('theme').value = 'slate';
  await h.elements.get('theme').listeners.change();
  assert.equal(h.elements.get('theme').value, 'nocturne');
  assert.equal(h.run('document.documentElement.dataset.theme'), 'nocturne');
});
