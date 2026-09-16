process.env.TZ = 'America/Los_Angeles';

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';
import { runAppScripts } from './app-scripts.mjs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
const response = (status, data) => ({ status, ok: status < 400, json: async () => data });
const tick = () => new Promise(resolve => setImmediate(resolve));
const weekOf = path => new URL(path, 'http://flexweek.test').searchParams.get('week_start');
const NOW = new Date(2026, 8, 10, 12, 0, 0);
const MONDAY = '2026-09-07';
const NEXT = '2026-09-14';

class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [NOW.getTime()])); }
  static now() { return NOW.getTime(); }
}

function harness() {
  const elements = new Map();
  const allElements = [];
  const local = new Map();
  const session = new Map();
  let handler = async () => response(401, { detail: 'Please sign in' });
  const requests = [];

  function descendants(root) {
    const found = [];
    function visit(item) { found.push(item); item.children.forEach(visit); }
    visit(root);
    return found;
  }

  function matches(el, selector) {
    if (selector.startsWith('.')) return el.classList.contains(selector.slice(1));
    const action = selector.match(/^button\[data-action="([^"]+)"\]$/);
    if (action) return el.dataset.action === action[1];
    return false;
  }

  function element() {
    const classes = new Set();
    const el = {
      value: '', textContent: '', hidden: false, disabled: false, checked: false,
      dataset: {}, style: {}, children: [], listeners: {}, open: false,
      get className() { return Array.from(classes).join(' '); },
      set className(value) {
        classes.clear();
        String(value).split(/\s+/).filter(Boolean).forEach(name => classes.add(name));
      },
      classList: { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name) },
      set innerHTML(_value) { this.children = []; },
      get innerHTML() { return ''; },
      addEventListener(name, fn) { this.listeners[name] = fn; },
      appendChild(child) { this.children.push(child); return child; },
      replaceChildren(...children) { this.children = children; },
      querySelector(selector) { return descendants(this).find(item => item !== this && matches(item, selector)) || null; },
      querySelectorAll(selector) { return descendants(this).filter(item => item !== this && matches(item, selector)); },
      closest() { return null; }, contains(node) { return descendants(this).includes(node); },
      showModal() { this.open = true; }, close() { this.open = false; },
      setAttribute(name) { if (name === 'open') this.open = true; }, removeAttribute(name) { if (name === 'open') this.open = false; },
      reset() {}, focus() {}, click() {}, scrollIntoView() {}, setPointerCapture() {}, releasePointerCapture() {},
      getBoundingClientRect() { return { top: 0, bottom: 100, left: 0, right: 100, height: 100, width: 100 }; },
    };
    allElements.push(el);
    return el;
  }

  for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], element());
  for (const match of html.matchAll(/<button\b[^>]*data-action="([^"]+)"[^>]*>/g)) {
    const button = element();
    button.dataset.action = match[1];
    elements.get('block-context-menu').appendChild(button);
  }

  const storage = map => ({
    get length() { return map.size; },
    key: index => Array.from(map.keys())[index] || null,
    getItem: key => map.has(key) ? map.get(key) : null,
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: key => map.delete(key),
  });

  const context = vm.createContext({
    document: {
      getElementById: id => { assert.ok(elements.has(id), `Missing HTML element ${id}`); return elements.get(id); },
      documentElement: { dataset: { theme: 'nocturne' } },
      createElement: element, addEventListener() {},
      querySelectorAll: selector => allElements.filter(item => matches(item, selector)),
    },
    window: { addEventListener() {} },
    localStorage: storage(local), sessionStorage: storage(session),
    fetch: async (path, options = {}) => { requests.push({ path, options }); return handler(path, options); },
    getComputedStyle: () => ({ getPropertyValue: () => '2.75rem' }),
    setTimeout, clearTimeout, setInterval, clearInterval, AbortController, structuredClone,
    console, crypto: globalThis.crypto, TextEncoder, confirm: () => true,
    Date: FixedDate, matchMedia: () => ({ matches: false, addEventListener() {} }),
  });
  runAppScripts(vm, context);

  return {
    elements, requests, allElements,
    run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    async login({ blocks = [], saved = [], owned = [], id = 1 } = {}) {
      await tick();
      handler = async path => {
        if (path.startsWith('/api/assignments')) return response(200, { assignments: owned });
        if (path.startsWith('/api/weeks')) return response(200, { weeks: saved });
        if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks, revision: 0 });
        return response(200, { theme: 'nocturne' });
      };
      await vm.runInContext(`loadAccount({id:${id},username:'student${id}'})`, context);
    },
  };
}

const fixed = (overrides = {}) => ({
  id: 'school', kind: 'locked', title: 'School', duration_min: 60,
  days: [0], start: '10:00', priority: 1, energy: 'medium', missed_days: [], ...overrides,
});

const assignment = (overrides = {}) => ({
  id: 'hw-essay', title: 'Essay', course: 'English', category: 'assignments',
  priority: 3, energy: 'medium', spotify_url: null, due: '2026-09-12T23:59',
  estimate_min: 120, focus_minutes: 0, focus_sessions: 0, completed: false,
  completed_at: null, revision: 1, planned_min: 0, unplanned_min: 120, ...overrides,
});

test('Stage 3 actions are visible and phone controls use a real 44px minimum', () => {
  for (const id of ['copy-day', 'paste-day', 'routine-save-open', 'routine-apply-open',
    'unfinished-open', 'prefs-routines', 'restore-create']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(css, /\.stage3-dialog \.form-actions button \{ min-height: 44px; \}/);
  assert.match(css, /\.week-nav button, \.week-menu > summary, \.week-menu-items button \{ min-height: 44px; \}/);
});

test('fixed paste previews collisions, keeps one stable retry, and saves a fresh clean block', async () => {
  const h = harness();
  const source = fixed({ completed: true, completed_day: 0, missed_days: [0], focus_minutes: 30 });
  await h.login({ blocks: [source] });
  assert.equal(h.run("copyBlockById('school', 0, 'block')"), true);
  assert.equal(h.run('pasteStage3Clipboard(0)'), true);
  assert.equal(h.run('stage3Preview.rows[0].checked'), false, 'the source occupies the pasted time');
  h.run("stage3Preview.rows[0].block.start = '11:00'; stage3Preview.rows[0].checked = true; renderStage3Preview()");

  const payloads = [];
  h.handle(async (_path, options) => {
    const body = JSON.parse(options.body);
    payloads.push(body);
    if (payloads.length === 1) return response(503, { detail: 'Reply lost' });
    return response(200, { weeks: body.weeks.map(week => ({ ...week, revision: 1 })), assignments: [] });
  });
  assert.equal(await h.run('confirmStage3Preview()'), false);
  assert.equal(await h.run('confirmStage3Preview()'), true);
  assert.equal(payloads[0].operation_id, payloads[1].operation_id);
  assert.equal(payloads[0].weeks[0].blocks[1].id, payloads[1].weeks[0].blocks[1].id);
  const pasted = payloads[1].weeks[0].blocks[1];
  assert.notEqual(pasted.id, source.id);
  assert.deepEqual([pasted.start, pasted.completed, pasted.completed_day, pasted.focus_minutes, pasted.missed_days],
    ['11:00', false, null, 0, []]);
  assert.equal(h.run('undoSteps.length'), 1);
});

test('occurrence copy splits one day while series copy keeps every weekday', async () => {
  const h = harness();
  await h.login({ blocks: [fixed({ days: [0, 2] })] });
  h.run("copyBlockById('school', 2, 'occurrence')");
  assert.deepEqual(JSON.parse(h.run('JSON.stringify(proposalsFromClipboard(4, null).map(row => row.day))')), [4]);
  h.run("copyBlockById('school', 2, 'series')");
  assert.deepEqual(JSON.parse(h.run('JSON.stringify(proposalsFromClipboard(4, null).map(row => row.day))')), [0, 2]);
});

test('homework copy stays flexible and linked, and cannot exceed unplanned time', async () => {
  const h = harness();
  const item = assignment({ focus_minutes: 30, unplanned_min: 30 });
  const sessionBlock = { id: 'session', kind: 'flexible', title: 'Essay', duration_min: 60,
    days: [3, 4], start: null, assignment_id: item.id, completed: false };
  await h.login({ blocks: [sessionBlock], owned: [item] });
  h.run("copyBlockById('session', 3, 'block')");
  const copied = h.run('proposalsFromClipboard(4, null)[0]');
  assert.deepEqual([copied.block.kind, copied.block.assignment_id, copied.block.start, copied.block.duration_min, copied.day],
    ['flexible', item.id, null, 30, 4]);
  assert.equal(copied.checked, true);
});

test('copy day omits completed homework and work with no actual placement', async () => {
  const h = harness();
  const open = { id: 'open', kind: 'flexible', title: 'Open', duration_min: 30, days: [0, 1], assignment_id: 'hw-open' };
  const done = { ...open, id: 'done', title: 'Done', assignment_id: 'hw-done', completed: true };
  await h.login({ blocks: [fixed(), open, done], owned: [assignment({ id: 'hw-open', title: 'Open' }), assignment({ id: 'hw-done', title: 'Done', completed: true })] });
  h.run("weekState().trace = {placed:[{...weekState().blocks[1], days:[0], start:'12:00'}]}");
  assert.equal(h.run('copyCurrentDay(0)'), true);
  assert.deepEqual(h.run('stage3Clipboard.items.map(item => item.block.id)'), ['school', 'open']);
});

test('keyboard shortcuts ignore form fields and account cleanup clears copied data', async () => {
  const h = harness();
  await h.login({ blocks: [fixed()] });
  h.run("selectBlock('school', 0)");
  const ignored = h.run("handleStage3Key({ctrlKey:true,metaKey:false,altKey:false,key:'c',target:{closest:()=>true},preventDefault(){}})");
  assert.equal(ignored, false);
  assert.equal(h.run('stage3Clipboard'), null);
  h.run("handleStage3Key({ctrlKey:true,metaKey:false,altKey:false,key:'c',target:{closest:()=>false},preventDefault(){}})");
  assert.ok(h.run('stage3Clipboard'));
  h.run('clearStage3State()');
  assert.equal(h.run('stage3Clipboard'), null);
});

test('keyboard paste uses the selected destination time and requires a meaningful day', async () => {
  const h = harness();
  await h.login({ blocks: [fixed(), fixed({ id: 'practice', days: [2], start: '15:00', title: 'Practice' })] });
  h.run("copyBlockById('school', 0, 'block'); selectBlock('practice', 2)");
  assert.equal(h.run("handleStage3Key({ctrlKey:true,metaKey:false,altKey:false,key:'v',target:{closest:()=>false},preventDefault(){}})"), true);
  assert.deepEqual([h.run('stage3Preview.rows[0].day'), h.run('stage3Preview.rows[0].block.start')], [2, '15:00']);

  h.run(`stage3Preview = null; selectedBlockId = null; selectedOccurrenceDay = null; selectedWeek = '${NEXT}'`);
  assert.equal(h.run('pasteStage3Clipboard()'), false);
  assert.match(h.elements.get('status').textContent, /Select a block or open Day view/);
});

test('paste preview disables confirmation before a week would exceed 100 blocks', async () => {
  const h = harness();
  const fillers = Array.from({ length: 99 }, (_item, index) => ({
    id: `f-${index}`, kind: 'flexible', title: `Task ${index}`, duration_min: 15,
    days: [0], start: null, completed: false,
  }));
  await h.login({ blocks: [fixed(), ...fillers] });
  h.run("copyBlockById('school', 0, 'block'); pasteStage3Clipboard(6, '20:00')");
  assert.equal(h.elements.get('stage3-preview-confirm').disabled, true);
  assert.match(h.elements.get('stage3-preview-error').textContent, /exceed 100 blocks/);
  assert.equal(await h.run('confirmStage3Preview()'), false);
  assert.equal(h.requests.filter(request => request.path === '/api/changes').length, 0);
});

test('routines save fixed commitments only and apply selected days with a recovery point', async () => {
  const h = harness();
  const homework = { id: 'session', kind: 'flexible', title: 'Essay', duration_min: 60, days: [3], assignment_id: 'hw-essay' };
  await h.login({ blocks: [fixed({ days: [0, 1], completed: true, missed_days: [0] }), homework], owned: [assignment()] });
  h.run('renderRoutineChoices()');
  h.elements.get('routine-name').value = 'School week';
  let savedRoutine;
  h.handle(async (path, options) => {
    const body = JSON.parse(options.body);
    assert.match(path, /^\/api\/routines\//);
    savedRoutine = { ...body, revision: 1 };
    return response(200, savedRoutine);
  });
  assert.equal(await h.run('saveNewRoutine()'), true);
  assert.equal(savedRoutine.blocks.length, 1);
  assert.deepEqual(savedRoutine.blocks[0].days, [0, 1]);
  assert.equal('completed' in savedRoutine.blocks[0], false);
  assert.equal('missed_days' in savedRoutine.blocks[0], false);

  h.elements.get('routine-destination').value = NEXT;
  h.elements.get('routine-day-0').checked = true;
  h.elements.get('routine-day-1').checked = false;
  let change;
  h.handle(async (path, options) => {
    if (path.startsWith('/api/week?')) return response(200, { week_start: NEXT, blocks: [], revision: 0 });
    change = JSON.parse(options.body);
    return response(200, { weeks: change.weeks.map(week => ({ ...week, revision: 1 })), assignments: [] });
  });
  assert.equal(await h.run(`applyRoutine('${savedRoutine.id}')`), true);
  assert.deepEqual(JSON.parse(h.run('JSON.stringify(stage3Preview.rows.map(row => row.day))')), [0]);
  h.run('stage3Preview.rows[0].block.duration_min = 45; renderStage3Preview()');
  assert.equal(await h.run('confirmStage3Preview()'), true);
  assert.match(change.snapshot_label, /Before applying School week/);
  assert.deepEqual(change.weeks[0].blocks[0].days, [0]);
  assert.equal(change.weeks[0].blocks[0].duration_min, 45);
  assert.equal(change.weeks[0].blocks[0].completed, false);
  assert.deepEqual(savedRoutine.blocks[0].days, [0, 1], 'one-week exceptions do not edit the saved routine');
  assert.equal(h.run('selectedWeek'), NEXT);
});

test('unfinished homework keeps assignment identity and repeated planning cannot add it twice', async () => {
  const h = harness();
  const item = assignment({ estimate_min: 120, focus_minutes: 30, unplanned_min: 90 });
  await h.login({ saved: ['2026-08-31'], owned: [item] });
  assert.equal(h.elements.get('unfinished-review').hidden, false);
  assert.equal(h.run("previewUnfinishedAssignment('hw-essay')"), true);
  assert.deepEqual(JSON.parse(h.run('JSON.stringify(stage3Preview.rows[0].block.days)')), [3, 4, 5]);
  assert.equal(h.run('stage3Preview.rows[0].block.assignment_id'), item.id);
  h.handle(async (_path, options) => {
    const body = JSON.parse(options.body);
    return response(200, { weeks: body.weeks.map(week => ({ ...week, revision: 1 })), assignments: [] });
  });
  assert.equal(await h.run('confirmStage3Preview()'), true);
  assert.equal(h.run("availableHomeworkMinutes('hw-essay')"), 0);
  assert.equal(h.run("previewUnfinishedAssignment('hw-essay')"), false);
  assert.equal(h.run('weekState().blocks.filter(block => block.assignment_id === "hw-essay").length'), 1);
});

test('a stale restore refreshes its preview, then clears clipboard and Undo after success', async () => {
  const h = harness();
  await h.login({ blocks: [fixed()] });
  let token = 'state-1';
  let restorePosts = 0;
  h.handle(async (path, options) => {
    if (path.endsWith('/preview')) return response(200, {
      id: 'rp-1', state_token: token, changes: { weeks: { added: [], changed: [MONDAY], removed: [] }, assignments: { added: [], changed: [], removed: [] } },
    });
    if (path.endsWith('/restore')) {
      restorePosts += 1;
      if (restorePosts === 1) { token = 'state-2'; return response(409, { detail: 'stale' }); }
      return response(200, { restored: true });
    }
    if (path.startsWith('/api/assignments')) return response(200, { assignments: [] });
    if (path.startsWith('/api/weeks')) return response(200, { weeks: [MONDAY] });
    if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks: [], revision: 2 });
    if (path === '/api/preferences') return response(200, { theme: 'nocturne' });
    return response(200, {});
  });
  h.run("copyBlockById('school', 0, 'block'); pushStep({label:'x',weeks:[],assignments:[]})");
  assert.equal(await h.run("previewRestorePoint('rp-1')"), true);
  assert.equal(await h.run('restoreFromPreview()'), false);
  assert.equal(h.run('stage3RestorePreview.state_token'), 'state-2');
  assert.equal(await h.run('restoreFromPreview()'), true);
  assert.equal(h.run('stage3Clipboard'), null);
  assert.equal(h.run('undoSteps.length'), 0);
});

test('Clear week rolls back on failure and reuses its operation id on retry', async () => {
  const h = harness();
  await h.login({ blocks: [fixed()] });
  const payloads = [];
  h.handle(async (_path, options) => {
    const body = JSON.parse(options.body);
    payloads.push(body);
    if (payloads.length === 1) return response(500, { detail: 'snapshot failed' });
    return response(200, { weeks: [{ ...body.weeks[0], revision: 1 }], assignments: [] });
  });
  assert.equal(await h.run('clearWeekWithRestore()'), false);
  assert.equal(h.run('weekState().blocks.length'), 1);
  assert.equal(await h.run('clearWeekWithRestore()'), true);
  assert.equal(payloads[0].operation_id, payloads[1].operation_id);
  assert.match(payloads[1].snapshot_label, /Before clearing/);
  assert.equal(h.run('weekState().blocks.length'), 0);
});

test('copied sessions of one homework share its remaining time, so a batch cannot over-plan it', async () => {
  const h = harness();
  const item = assignment({ estimate_min: 150, unplanned_min: 30 });
  const first = { id: 's1', kind: 'flexible', title: 'Essay', duration_min: 60, days: [0], start: '12:00', assignment_id: item.id };
  const second = { ...first, id: 's2', start: '14:00' };
  await h.login({ blocks: [first, second], owned: [item] });
  assert.equal(h.run('copyCurrentDay(0)'), true);
  const rows = JSON.parse(h.run('JSON.stringify(proposalsFromClipboard(2, null).map(row => [row.checked, row.block.duration_min, row.invalid]))'));
  assert.deepEqual(rows, [[true, 30, ''], [false, 60, 'No unplanned time remains for this homework.']]);
});

test('a routine with a long name still applies, with its restore point label cut to 80 characters', async () => {
  const h = harness();
  await h.login({ blocks: [] });
  const routine = {
    id: 'r-long', name: 'Monday to Friday school week with swim practice and orchestra rehearsal', revision: 1,
    blocks: [{ template_id: 't-1', title: 'School', days: [0], start: '08:00', duration_min: 60 }],
  };
  h.run(`stage3Routines.set('r-long', ${JSON.stringify(routine)})`);
  h.elements.get('routine-destination').value = NEXT;
  h.elements.get('routine-day-0').checked = true;
  let change;
  h.handle(async (path, options) => {
    if (path.startsWith('/api/week?')) return response(200, { week_start: NEXT, blocks: [], revision: 0 });
    change = JSON.parse(options.body);
    return response(200, { weeks: change.weeks.map(week => ({ ...week, revision: 1 })), assignments: [] });
  });
  assert.equal(await h.run("applyRoutine('r-long')"), true);
  assert.equal(await h.run('confirmStage3Preview()'), true);
  assert.equal(Array.from(change.snapshot_label).length, 80);
  assert.match(change.snapshot_label, /^Before applying Monday to Friday school week/);
});

test('a preview save refused with 409 keeps Save off, and the next paste is a new operation', async () => {
  const h = harness();
  await h.login({ blocks: [fixed()] });
  h.run("copyBlockById('school', 0, 'block'); pasteStage3Clipboard(2, '12:00')");
  const payloads = [];
  h.handle(async (_path, options) => {
    const body = JSON.parse(options.body);
    payloads.push(body);
    if (payloads.length === 1) return response(409, { detail: 'This operation id was already used for different changes.' });
    return response(200, { weeks: body.weeks.map(week => ({ ...week, revision: 1 })), assignments: [] });
  });
  assert.equal(await h.run('confirmStage3Preview()'), false);
  assert.match(h.elements.get('stage3-preview-error').textContent, /reload the week/);
  assert.equal(h.elements.get('stage3-preview-confirm').disabled, true);
  assert.equal(await h.run('confirmStage3Preview()'), false, 'the out-of-date preview cannot be saved again');
  assert.equal(payloads.length, 1);

  h.run("stage3Preview = null; pasteStage3Clipboard(2, '12:00')");
  assert.equal(await h.run('confirmStage3Preview()'), true);
  assert.notEqual(payloads[0].operation_id, payloads[1].operation_id);
  assert.notEqual(payloads[0].weeks[0].blocks[1].id, payloads[1].weeks[0].blocks[1].id);
});

test('a restore keeps the student on the week they were looking at', async () => {
  const h = harness();
  await h.login({ blocks: [fixed()] });
  h.handle(async path => {
    if (path.endsWith('/preview')) return response(200, { id: 'rp-1', state_token: 'state-1',
      changes: { weeks: { added: [], changed: [NEXT], removed: [] }, assignments: { added: [], changed: [], removed: [] } } });
    if (path.endsWith('/restore')) return response(200, { restored: true });
    if (path.startsWith('/api/assignments')) return response(200, { assignments: [] });
    if (path.startsWith('/api/weeks')) return response(200, { weeks: [MONDAY, NEXT] });
    if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks: [], revision: 3 });
    return response(200, { theme: 'nocturne' });
  });
  assert.equal(await h.run(`selectWeek('${NEXT}')`), true);
  assert.equal(await h.run("previewRestorePoint('rp-1')"), true);
  assert.equal(await h.run('restoreFromPreview()'), true);
  assert.equal(h.run('selectedWeek'), NEXT);
});

test('shortcuts do nothing while a dialog is open, even when focus fell back to the page', async () => {
  const h = harness();
  await h.login({ blocks: [fixed()] });
  h.run("selectBlock('school', 0)");
  h.run("document.querySelector = selector => selector === 'dialog[open]' ? {} : null");
  const press = key => h.run(`handleStage3Key({ctrlKey:true,metaKey:false,altKey:false,key:'${key}',target:null,preventDefault(){}})`);
  assert.equal(press('c'), false);
  assert.equal(h.run('stage3Clipboard'), null);
  assert.equal(h.run("handleHistoryKey({ctrlKey:true,metaKey:false,altKey:false,key:'z',target:null,preventDefault(){}})"), false);
});

test('an invalid preview row starts unchecked', async () => {
  const h = harness();
  await h.login({ blocks: [] });
  h.run(`stage3Clipboard = { kind: 'block', label: 'Loose', fingerprint: 'loose', items: [{
    block: { id: 'loose', kind: 'locked', title: 'Loose', duration_min: 60, days: [1], start: null },
    sourceDay: 1, scope: 'block', groupId: 'g-loose' }] }`);
  assert.equal(h.run('pasteStage3Clipboard(1, null)'), true);
  assert.equal(h.run('stage3Preview.rows[0].invalid'), 'Choose a start time.');
  assert.equal(h.run('stage3Preview.rows[0].checked'), false);
});
