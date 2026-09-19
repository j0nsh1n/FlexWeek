process.env.TZ = 'America/Los_Angeles';

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';
import { runAppScripts } from './app-scripts.mjs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const response = (status, data) => ({ status, ok: status < 400, json: async () => data });
const tick = () => new Promise(resolve => setImmediate(resolve));
const weekOf = path => new URL(path, 'http://flexweek.test').searchParams.get('week_start');
const NOW = new Date(2026, 8, 10, 12, 0, 0);
const MONDAY = '2026-09-07';
const NEXT = '2026-09-14';
const NOON = new Date(2026, 8, 10, 12, 0, 0);
const SEVEN_PAST = new Date(2026, 8, 10, 12, 7, 0);
const BEFORE_SIX = new Date(2026, 8, 10, 5, 0, 0);
const TEN_TO_ELEVEN = new Date(2026, 8, 10, 22, 50, 0);
const AT_ELEVEN = new Date(2026, 8, 10, 23, 0, 0);

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
      dataset: {}, children: [], listeners: {}, open: false,
      style: { setProperty(name, value) { this[name] = value; }, removeProperty(name) { delete this[name]; } },
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
    elements, requests,
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

const school = (overrides = {}) => ({
  id: 'school', kind: 'locked', title: 'School', duration_min: 390,
  days: [0, 1, 2, 3, 4], start: '08:00', priority: 1, energy: 'medium', missed_days: [], ...overrides,
});

const homework = (overrides = {}) => ({
  id: 'session', kind: 'flexible', title: 'Essay', duration_min: 60,
  days: [3, 4], start: '16:00', priority: 3, energy: 'medium',
  assignment_id: 'hw-essay', completed: false, missed_days: [], ...overrides,
});

function emptyTrace(overrides = {}) {
  return {
    placed: [], unplaced: [], moves: [], explanations: [],
    failed_constraints: [], solve_ms: 1, complete: true, ...overrides,
  };
}

function lateTrace(overrides = {}) {
  return emptyTrace({
    placed: [school(), homework({ start: '16:30' })],
    unplaced: [{ id: 'overflow', title: 'Lab report', kind: 'flexible', duration_min: 60, days: [3] }],
    moves: [{
      block_id: 'session', reason: 'RESHUFFLE_AFTER_MISS',
      from_day: 3, from_start: '16:00', to_day: 3, to_start: '16:30',
    }],
    ...overrides,
  });
}

function changesReply(body) {
  return {
    weeks: body.weeks.map(week => ({ ...week, revision: week.revision + 1 })),
    assignments: body.assignments || [],
  };
}

async function previewLate(h, { minutes = 30, now, trace = lateTrace(), existing } = {}) {
  if (existing) h.run(`weekState().trace = ${JSON.stringify({ placed: existing })}`);
  h.elements.get('late-minutes').value = String(minutes);
  const solves = [];
  h.handle(async (path, options) => {
    assert.equal(path, '/api/solve');
    solves.push(JSON.parse(options.body));
    return response(200, trace);
  });
  const opened = now
    ? await h.run(`openRunningLate(new Date(${now.getTime()}))`)
    : h.run('openRunningLate()');
  assert.equal(opened, true);
  const previewed = now
    ? await h.run(`previewRunningLate(new Date(${now.getTime()}))`)
    : await h.run('previewRunningLate()');
  return { previewed, solves };
}

test('Running late stays on this week, daylight hours, and snaps down to 15 minutes', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal(await h.run(`selectWeek('${NEXT}')`), true);
  assert.equal(h.run('openRunningLate()'), false);
  assert.match(h.elements.get('status').textContent, /Open this week/);

  assert.equal(await h.run(`selectWeek('${MONDAY}')`), true);
  assert.equal(await h.run(`openRunningLate(new Date(${BEFORE_SIX.getTime()}))`), false);
  assert.match(h.elements.get('status').textContent, /06:00 and 23:00/);
  assert.equal(await h.run(`openRunningLate(new Date(${AT_ELEVEN.getTime()}))`), false);

  assert.equal(await h.run(`openRunningLate(new Date(${SEVEN_PAST.getTime()}))`), true);
  assert.match(h.elements.get('late-context').textContent, /Starting from 12:00 today \(Thursday\)/);
  assert.equal(h.run(`lateStart(currentDateInfo(new Date(${SEVEN_PAST.getTime()})))`), 12 * 60);
});

test('preview sends the exact running_late request for 15, 30 and 60 minutes', async () => {
  for (const minutes of [15, 30, 60]) {
    const h = harness();
    await h.login({ blocks: [school(), homework()] });
    h.run(`weekState().trace = ${JSON.stringify({ placed: [school(), homework()] })}`);
    const { previewed, solves } = await previewLate(h, { minutes, existing: [school(), homework()] });
    assert.equal(previewed, true);
    assert.equal(solves.length, 1);
    assert.deepEqual(solves[0].running_late, {
      day: 3, minutes, from_start: '12:00', previous_placed: [school(), homework()],
    });
    assert.equal(solves[0].week_start, MONDAY);
  }
});

test('an existing plan sends one solve; no plan sends a baseline then the late solve', async () => {
  const withTrace = harness();
  await withTrace.login({ blocks: [school(), homework()] });
  const planned = await previewLate(withTrace, { existing: [school(), homework()] });
  assert.equal(planned.previewed, true);
  assert.equal(planned.solves.length, 1);
  assert.ok(planned.solves[0].running_late);
  assert.equal(withTrace.requests.filter(item => item.path === '/api/changes').length, 0);

  const cold = harness();
  await cold.login({ blocks: [school(), homework()] });
  const unplanned = await previewLate(cold);
  assert.equal(unplanned.previewed, true);
  assert.equal(unplanned.solves.length, 2);
  assert.equal(unplanned.solves[0].running_late, undefined);
  assert.equal(unplanned.solves[1].running_late.minutes, 30);
});

test('preview lists moves and unplaced homework without writing the week', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  const { previewed } = await previewLate(h, { existing: [school(), homework()] });
  assert.equal(previewed, true);
  assert.match(h.elements.get('late-summary').textContent, /1 task moves · 1 task no longer fits/);
  assert.match(h.elements.get('late-changes').children[0].textContent, /Essay: Thursday 16:00 → Thursday 16:30/);
  assert.match(h.elements.get('late-changes').children[1].textContent, /Lab report no longer fits/);
  assert.equal(h.elements.get('late-preview').hidden, false);
  assert.equal(h.elements.get('late-accept').hidden, false);
  assert.equal(h.run(`weekState().blocks.map(block => block.id).join(',')`), 'school,session');
  assert.equal(h.requests.filter(item => item.path === '/api/changes').length, 0);
});

test('accept adds exactly one locked late block and keeps every existing task and fixed commitment', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()] })).previewed, true);
  let saved;
  h.handle(async (path, options) => {
    if (path === '/api/solve') return response(200, emptyTrace({ placed: [school(), homework()] }));
    assert.equal(path, '/api/changes');
    saved = JSON.parse(options.body);
    return response(200, changesReply(saved));
  });
  assert.equal(await h.run('acceptRunningLate()'), true);
  const ids = saved.weeks[0].blocks.map(block => block.id);
  const late = saved.weeks[0].blocks.filter(block => block.title === 'Running late');
  assert.equal(late.length, 1);
  assert.equal(late[0].kind, 'locked');
  assert.equal(late[0].start, '12:00');
  assert.equal(late[0].duration_min, 30);
  assert.deepEqual(late[0].days, [3]);
  assert.ok(ids.includes('school') && ids.includes('session'));
  assert.equal(saved.weeks[0].blocks.length, 3);
  assert.equal(h.run(`weekState().blocks.filter(block => block.title === 'School').length`), 1);
  assert.equal(h.run(`weekState().blocks.filter(block => block.id === 'session').length`), 1);
});

test('a failed save leaves the week alone and retries the same operation id and block id', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()] })).previewed, true);
  const firstId = h.run('latePreview.block.id');
  const firstOp = h.run('latePreview.operationId');
  const operations = [];
  const blockIds = [];
  let attempt = 0;
  h.handle(async (path, options) => {
    if (path === '/api/solve') return response(200, emptyTrace());
    assert.equal(path, '/api/changes');
    const body = JSON.parse(options.body);
    operations.push(body.operation_id);
    blockIds.push(body.weeks[0].blocks.find(block => block.title === 'Running late').id);
    attempt += 1;
    return attempt === 1 ? response(503, { detail: 'Try again' }) : response(200, changesReply(body));
  });
  assert.equal(await h.run('acceptRunningLate()'), false);
  assert.equal(h.run(`weekState().blocks.map(block => block.id).join(',')`), 'school,session');
  assert.equal(await h.run('acceptRunningLate()'), true);
  assert.deepEqual(operations, [firstOp, firstOp]);
  assert.deepEqual(blockIds, [firstId, firstId]);
});

test('a 409 makes the running-late preview stale', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()] })).previewed, true);
  h.handle(async () => response(409, { detail: 'This week changed in another window. Reload before saving.' }));
  assert.equal(await h.run('acceptRunningLate()'), false);
  assert.equal(h.run('latePreview.stale'), true);
  assert.equal(h.elements.get('late-accept').disabled, true);
  assert.match(h.elements.get('late-error').textContent, /changed elsewhere/);
  assert.equal(h.run(`weekState().blocks.map(block => block.id).join(',')`), 'school,session');
});

test('accept records one Undo step that removes the late block', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()] })).previewed, true);
  h.handle(async (path, options) => {
    if (path === '/api/solve') return response(200, emptyTrace());
    const body = JSON.parse(options.body);
    if (path === '/api/changes') return response(200, changesReply(body));
    if (path === '/api/week' && options.method === 'PUT') {
      return response(200, { ...body, revision: body.revision + 1 });
    }
    return response(200, {});
  });
  assert.equal(await h.run('acceptRunningLate()'), true);
  assert.equal(h.run('undoSteps.length'), 1);
  assert.equal(h.run(`weekState().blocks.filter(block => block.title === 'Running late').length`), 1);
  assert.equal(await h.run('undo()'), true);
  assert.equal(h.run(`weekState().blocks.filter(block => block.title === 'Running late').length`), 0);
  assert.deepEqual(h.run(`weekState().blocks.map(block => block.id)`), ['school', 'session']);
});

test('a delay near 23:00 is clipped to a valid 15-minute block', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  h.elements.get('late-minutes').value = '60';
  h.handle(async (path, options) => {
    assert.equal(path, '/api/solve');
    const body = JSON.parse(options.body);
    assert.equal(body.running_late.from_start, '22:45');
    assert.equal(body.running_late.minutes, 60);
    return response(200, emptyTrace());
  });
  assert.equal(await h.run(`openRunningLate(new Date(${TEN_TO_ELEVEN.getTime()}))`), true);
  h.run(`weekState().trace = ${JSON.stringify({ placed: [school()] })}`);
  assert.equal(await h.run(`previewRunningLate(new Date(${TEN_TO_ELEVEN.getTime()}))`), true);
  assert.equal(h.run('latePreview.block.start'), '22:45');
  assert.equal(h.run('latePreview.block.duration_min'), 15);
});

test('account changes and stale solves cannot affect the next account', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()], id: 1 });
  h.elements.get('late-minutes').value = '30';
  h.run(`weekState().trace = ${JSON.stringify({ placed: [school()] })}`);
  h.handle(async (path, options) => {
    if (path === '/api/solve') {
      h.run("epoch += 1; account = {id: 2, username: 'student2'}");
      return response(200, lateTrace());
    }
    return response(200, { week_start: weekOf(path), blocks: [], revision: 0 });
  });
  assert.equal(h.run('openRunningLate()'), true);
  assert.equal(await h.run('previewRunningLate()'), false);
  assert.equal(h.run('latePreview'), null);
  assert.equal(h.elements.get('late-preview').hidden, true);
  assert.equal(h.run('account.id'), 2);
});

test('the 100-block limit prevents accepting a late start', async () => {
  const h = harness();
  const blocks = Array.from({ length: 100 }, (_, index) => school({ id: 'fixed-' + index, days: [0] }));
  await h.login({ blocks });
  assert.equal(h.run('openRunningLate()'), false);
  assert.match(h.elements.get('status').textContent, /100 blocks/);
  assert.equal(h.elements.get('late-dialog').open, false);
});

test('reload and re-solve keep the accepted late interval', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()] })).previewed, true);
  let stored;
  const solves = [];
  h.handle(async (path, options) => {
    if (path === '/api/changes') {
      const body = JSON.parse(options.body);
      stored = body.weeks[0].blocks;
      return response(200, changesReply(body));
    }
    if (path === '/api/solve') {
      solves.push(JSON.parse(options.body));
      return response(200, emptyTrace({ placed: stored }));
    }
    if (path.startsWith('/api/week')) {
      return response(200, { week_start: weekOf(path), blocks: stored, revision: 1 });
    }
    if (path.startsWith('/api/assignments')) return response(200, { assignments: [] });
    if (path.startsWith('/api/weeks')) return response(200, { weeks: [] });
    return response(200, { theme: 'nocturne' });
  });
  assert.equal(await h.run('acceptRunningLate()'), true);
  const late = stored.find(block => block.title === 'Running late');
  assert.ok(late);
  assert.ok(solves[0].blocks.some(block => block.id === late.id && block.start === '12:00' && block.duration_min === 30));
  await h.run("loadAccount({id:1,username:'student1'})");
  assert.equal(h.run(`weekState().blocks.filter(block => block.id === ${JSON.stringify(late.id)}).length`), 1);
  await h.run('solveWeek()');
  const again = solves[solves.length - 1];
  assert.equal(again.running_late, undefined);
  assert.ok(again.blocks.some(block => block.id === late.id && block.kind === 'locked' && block.duration_min === 30));
});

test('the Preview button says it is replanning while the solve is out', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal(h.run('openRunningLate()'), true);
  h.elements.get('late-minutes').value = '30';
  // The fake DOM builds elements from ids alone, so give the button its real words first.
  h.elements.get('late-preview-button').textContent = 'Preview new plan';
  h.run(`weekState().trace = ${JSON.stringify({ placed: [school(), homework()] })}`);
  let duringRequest = null;
  h.handle(async () => {
    duringRequest = h.elements.get('late-preview-button').textContent;
    return response(200, lateTrace());
  });
  assert.equal(await h.run('previewRunningLate()'), true);
  assert.equal(duringRequest, 'Replanning\u2026');
  assert.equal(h.elements.get('late-preview-button').textContent, 'Preview new plan');
  assert.equal(h.elements.get('late-preview-button').disabled, false);
});

test('every Running late refusal reaches the toast, not only the status line', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal(await h.run(`selectWeek('${NEXT}')`), true);

  assert.equal(h.run('openRunningLate()'), false);
  assert.equal(h.elements.get('reminder-toast').hidden, false);
  assert.match(h.elements.get('reminder-toast').textContent, /Open this week before using Running late\./);

  assert.equal(await h.run(`selectWeek('${MONDAY}')`), true);
  h.elements.get('reminder-toast').textContent = '';
  assert.equal(await h.run(`openRunningLate(new Date(${BEFORE_SIX.getTime()}))`), false);
  assert.match(h.elements.get('reminder-toast').textContent, /between 06:00 and 23:00\./);
});

test('the dialog explains a preview it cannot run instead of going quiet', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal(h.run('openRunningLate()'), true);
  h.elements.get('late-minutes').value = '30';
  // The week goes dirty while the dialog sits open, which used to make Preview do nothing at all.
  h.run('weekState().dirty = true');
  assert.equal(await h.run('previewRunningLate()'), false);
  assert.equal(h.elements.get('late-error').hidden, false);
  assert.match(h.elements.get('late-error').textContent, /changed while the dialog was open/);
  assert.equal(h.elements.get('late-preview').hidden, true);
});

test('accepting says what happened, including when no homework had to move', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  const quiet = emptyTrace({ placed: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()], trace: quiet })).previewed, true);
  assert.equal(h.elements.get('late-summary').textContent, '0 tasks move · 0 tasks no longer fit');
  h.handle(async (path, options) => {
    if (path === '/api/solve') return response(200, quiet);
    assert.equal(path, '/api/changes');
    return response(200, changesReply(JSON.parse(options.body)));
  });
  assert.equal(await h.run('acceptRunningLate()'), true);
  assert.match(h.elements.get('status').textContent, /Late start saved\. Nothing had to move\./);
  assert.match(h.elements.get('reminder-toast').textContent, /Late start saved\. Nothing had to move\./);
});

test('accepting counts the homework that moved', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()] })).previewed, true);
  h.handle(async (path, options) => {
    if (path === '/api/solve') return response(200, emptyTrace({ placed: [school(), homework()] }));
    return response(200, changesReply(JSON.parse(options.body)));
  });
  assert.equal(await h.run('acceptRunningLate()'), true);
  assert.match(h.elements.get('status').textContent, /Late start saved and 1 task moved\./);
});

function gridBlocks(h) {
  const found = [];
  (function visit(el) {
    el.children.forEach(child => { found.push(child); visit(child); });
  })(h.elements.get('week'));
  return found.filter(el => el.classList.contains('block'));
}

test('the accepted late block draws itself onto the grid, once', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()] })).previewed, true);
  const lateId = h.run('latePreview.block.id');
  h.handle(async (path, options) => {
    if (path === '/api/solve') {
      const body = JSON.parse(options.body);
      return response(200, emptyTrace({ placed: body.blocks.filter(block => block.kind === 'locked') }));
    }
    return response(200, changesReply(JSON.parse(options.body)));
  });
  assert.equal(await h.run('acceptRunningLate()'), true);

  const drawn = gridBlocks(h).filter(el => el.classList.contains('is-drawn-on'));
  assert.equal(drawn.length, 1, 'only the late block draws on');
  assert.equal(drawn[0].dataset.id, lateId);

  // An ordinary redraw must not replay it.
  h.run('renderWeek()');
  assert.equal(gridBlocks(h).filter(el => el.classList.contains('is-drawn-on')).length, 0);
});

test('a failed re-plan does not leave the late block waiting to animate', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()] })).previewed, true);
  h.handle(async (path, options) => {
    if (path === '/api/solve') return response(503, { detail: 'Planner busy' });
    return response(200, changesReply(JSON.parse(options.body)));
  });
  assert.equal(await h.run('acceptRunningLate()'), true);
  assert.equal(h.run('drawOnBlockId'), null);
  h.run('renderWeek()');
  assert.equal(gridBlocks(h).filter(el => el.classList.contains('is-drawn-on')).length, 0);
});

test('a failed re-plan after accept keeps the error instead of a success status', async () => {
  const h = harness();
  await h.login({ blocks: [school(), homework()] });
  assert.equal((await previewLate(h, { existing: [school(), homework()] })).previewed, true);
  h.handle(async (path, options) => {
    if (path === '/api/changes') {
      const body = JSON.parse(options.body);
      return response(200, changesReply(body));
    }
    if (path === '/api/solve') return response(503, { detail: 'Planner busy' });
    return response(200, {});
  });
  assert.equal(await h.run('acceptRunningLate()'), true);
  assert.match(h.elements.get('status').textContent, /Could not plan\. Planner busy/);
  assert.doesNotMatch(h.elements.get('status').textContent, /Saved the late start/);
});

test('a calendar block carries its category colour as --block-color, and no colour when it has none', async () => {
  const h = harness();
  await h.login({ blocks: [school({ category: 'class' }), school({ id: 'plain', days: [1] })] });
  const blocks = gridBlocks(h);
  const colored = blocks.filter(el => el.dataset.id === 'school');
  assert.ok(colored.length >= 1);
  for (const el of colored) {
    assert.equal(el.style['--block-color'], '#3b82f6');
    assert.equal(el.classList.contains('is-colored'), true);
    assert.equal(el.style.borderLeftColor, undefined, 'the colour goes through the property, not inline');
  }
  const plain = blocks.find(el => el.dataset.id === 'plain');
  assert.ok(plain);
  assert.equal(plain.style['--block-color'], undefined);
  assert.equal(plain.classList.contains('is-colored'), false);
});
