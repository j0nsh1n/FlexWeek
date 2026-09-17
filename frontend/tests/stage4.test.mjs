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

const sessionBlock = (overrides = {}) => ({
  id: 'session', kind: 'flexible', title: 'Essay', duration_min: 120,
  days: [0, 1, 2, 3, 4], start: null, priority: 3, energy: 'medium',
  assignment_id: 'hw-essay', completed: false, missed_days: [], ...overrides,
});

function storedAssignment(overrides = {}) {
  const item = assignment(overrides);
  delete item.revision;
  delete item.planned_min;
  delete item.unplanned_min;
  return item;
}

function changesReply(body) {
  return {
    weeks: body.weeks.map(week => ({ ...week, revision: week.revision + 1 })),
    assignments: body.assignments.map(change => ({
      id: change.id, revision: change.revision + 1, assignment: change.assignment,
    })),
  };
}

test('editing a homework keeps project details in the saved assignment', async () => {
  const h = harness();
  const item = assignment({
    notes: 'Compare the two primary sources.',
    links: [{ label: 'Prompt', url: 'https://school.example/essay' }],
    checklist: [{ id: 'outline', text: 'Write outline', done: false }],
  });
  await h.login({ blocks: [sessionBlock()], owned: [item] });
  assert.equal(h.run("openHomeworkDialog('hw-essay')"), true);
  assert.equal(h.elements.get('hw-notes').value, item.notes);
  assert.equal(h.run('projectLinkRows[0].label.value'), 'Prompt');
  assert.equal(h.run('projectCheckRows[0].text.value'), 'Write outline');

  h.elements.get('hw-title').value = 'Revised essay';
  let saved;
  h.handle(async (path, options) => {
    assert.equal(path, '/api/changes');
    saved = JSON.parse(options.body);
    return response(200, changesReply(saved));
  });
  assert.equal(h.run('saveHomework()'), true);
  await tick();
  assert.equal(saved.assignments[0].assignment.title, 'Revised essay');
  assert.equal(saved.assignments[0].assignment.notes, item.notes);
  assert.deepEqual(saved.assignments[0].assignment.links, item.links);
  assert.deepEqual(saved.assignments[0].assignment.checklist, item.checklist);
});

test('checking a project step does not finish its homework', async () => {
  const h = harness();
  const item = assignment({
    checklist: [{ id: 'sources', text: 'Collect sources', done: false }],
  });
  await h.login({ blocks: [sessionBlock()], owned: [item] });
  h.run("openHomeworkDialog('hw-essay'); projectCheckRows[0].done.checked = true");
  let saved;
  h.handle(async (_path, options) => {
    saved = JSON.parse(options.body);
    return response(200, changesReply(saved));
  });
  h.run('saveHomework()');
  await tick();
  assert.equal(saved.assignments[0].assignment.checklist[0].done, true);
  assert.equal(saved.assignments[0].assignment.completed, false);
  assert.equal(saved.assignments[0].assignment.completed_at, null);
});

test('removing project rows clears them from the stored assignment', async () => {
  const h = harness();
  const item = assignment({
    links: [{ label: 'Prompt', url: 'https://school.example/prompt' }],
    checklist: [{ id: 'draft', text: 'Draft', done: false }],
  });
  await h.login({ blocks: [sessionBlock()], owned: [item] });
  h.run("openHomeworkDialog('hw-essay'); projectLinkRows[0].root.children[2].listeners.click(); " +
    "projectCheckRows[0].root.children[2].listeners.click()");
  let saved;
  h.handle(async (_path, options) => {
    saved = JSON.parse(options.body);
    return response(200, changesReply(saved));
  });
  h.run('saveHomework()');
  await tick();
  assert.equal('links' in saved.assignments[0].assignment, false);
  assert.equal('checklist' in saved.assignments[0].assignment, false);
});

test('week JSON round-trips assignment notes, links, and checklist', async () => {
  const h = harness();
  const item = assignment({
    notes: 'Use chapters 3 and 4.',
    links: [{ label: 'Rubric', url: 'https://school.example/rubric?week=4' }],
    checklist: [{ id: 'draft', text: 'Draft', done: true }],
  });
  await h.login({ blocks: [sessionBlock()], owned: [item] });
  const payload = JSON.parse(h.run(`JSON.stringify(exportWeekPayload('${MONDAY}', weekState().blocks))`));
  assert.deepEqual(payload.assignments[0].notes, item.notes);
  assert.deepEqual(payload.assignments[0].links, item.links);
  assert.deepEqual(payload.assignments[0].checklist, item.checklist);
  const parsed = JSON.parse(h.run(`JSON.stringify(parseImportPayload(${JSON.stringify(JSON.stringify(payload))}))`));
  assert.equal(parsed.error, undefined);
  assert.deepEqual(parsed.assignments[0].notes, item.notes);
  assert.deepEqual(parsed.assignments[0].links, item.links);
  assert.deepEqual(parsed.assignments[0].checklist, item.checklist);
});

test('unsafe project metadata is refused before import can save', async () => {
  const h = harness();
  await h.login();
  const before = h.requests.filter(request => request.options && request.options.method).length;
  const cases = [
    storedAssignment({ links: [{ label: 'Bad', url: 'javascript:alert(1)' }] }),
    storedAssignment({ links: [{ label: 'Bad', url: 'https://student:secret@school.example/file' }] }),
    storedAssignment({ checklist: [
      { id: 'same', text: 'First', done: false },
      { id: 'same', text: 'Second', done: false },
    ] }),
  ];
  for (const item of cases) {
    const payload = { format: 'flexweek-week', version: 2, week_start: MONDAY,
      blocks: [sessionBlock()], assignments: [item] };
    const parsed = h.run(`parseImportPayload(${JSON.stringify(JSON.stringify(payload))})`);
    assert.match(parsed.error, /bad link|repeats a checklist id/i);
    assert.equal(await h.run(`importPayloadIntoWeek(parseImportPayload(${JSON.stringify(JSON.stringify(payload))}))`), false);
  }
  assert.equal(h.requests.filter(request => request.options && request.options.method).length, before);
});

test('project detail row limits stop before an oversized assignment can be built', async () => {
  const h = harness();
  await h.login();
  h.run('openHomeworkDialog()');
  for (let index = 0; index < 20; index += 1) assert.equal(h.run('addProjectLink(null)'), true);
  assert.equal(h.run('addProjectLink(null)'), false);
  assert.equal(h.run('projectLinkRows.length'), 20);
  assert.match(h.elements.get('hw-error').textContent, /Up to 20 links/);
  for (let index = 0; index < 40; index += 1) assert.equal(h.run('addProjectCheck(null)'), true);
  assert.equal(h.run('addProjectCheck(null)'), false);
  assert.equal(h.run('projectCheckRows.length'), 40);
  assert.match(h.elements.get('hw-error').textContent, /Up to 40 steps/);
});

test('Spread across days appears only for existing unfinished homework', async () => {
  const h = harness();
  const open = assignment({ due: '2026-09-16T21:00' });
  await h.login({ owned: [open] });
  h.run('openHomeworkDialog()');
  assert.equal(h.elements.get('hw-spread').hidden, true);
  h.run("openHomeworkDialog('hw-essay')");
  assert.equal(h.elements.get('hw-spread').hidden, false);

  const completed = assignment({ completed: true, completed_at: '2026-09-10T12:00' });
  h.run(`assignments.set('hw-essay', ${JSON.stringify(completed)}); openHomeworkDialog('hw-essay')`);
  assert.equal(h.elements.get('hw-spread').hidden, true);
});

test('the Spread button says it is working while the preview is out', async () => {
  const h = harness();
  const item = assignment({ due: '2026-09-16T21:00', estimate_min: 240, unplanned_min: 240 });
  await h.login({ owned: [item] });
  h.run("openHomeworkDialog('hw-essay'); openSpreadDialog('hw-essay')");
  h.elements.get('spread-session').value = '60';
  h.elements.get('spread-from').value = '2026-09-10';
  // The fake DOM builds elements from ids alone, so give the button its real words first.
  h.elements.get('spread-preview').textContent = 'Preview sessions';
  let duringRequest = null;
  h.handle(async () => {
    duringRequest = h.elements.get('spread-preview').textContent;
    return response(200, {
      assignment_id: 'hw-essay', session_min: 60, remaining_min: 0,
      sessions: [{ week_start: MONDAY, date: '2026-09-10', days: [3], duration_min: 60 }],
    });
  });
  assert.equal(await h.run('previewSpread()'), true);
  assert.equal(duringRequest, 'Working out sessions\u2026');
  assert.equal(h.elements.get('spread-preview').textContent, 'Preview sessions');
  assert.equal(h.elements.get('spread-preview').disabled, false);
});

test('spread previews distinct normal sessions and saves every week in one Undo step', async () => {
  const h = harness();
  const item = assignment({ due: '2026-09-16T21:00', estimate_min: 240, unplanned_min: 240 });
  await h.login({ owned: [item] });
  h.run("openHomeworkDialog('hw-essay'); openSpreadDialog('hw-essay')");
  h.elements.get('spread-session').value = '60';
  h.elements.get('spread-from').value = '2026-09-10';
  let spreadRequest;
  h.handle(async (path, options) => {
    assert.equal(path, '/api/assignments/hw-essay/spread');
    spreadRequest = JSON.parse(options.body);
    return response(200, {
      assignment_id: 'hw-essay', session_min: 60, remaining_min: 0,
      sessions: [
        { week_start: MONDAY, date: '2026-09-10', days: [3], duration_min: 60 },
        { week_start: MONDAY, date: '2026-09-10', days: [3], duration_min: 60 },
        { week_start: NEXT, date: '2026-09-14', days: [0], duration_min: 60 },
      ],
    });
  });
  assert.equal(await h.run('previewSpread()'), true);
  assert.deepEqual(spreadRequest, { session_min: 60, from_date: '2026-09-10' });
  assert.equal(h.elements.get('spread-dialog').open, false);
  assert.equal(h.elements.get('stage3-preview-dialog').open, true);
  assert.match(h.elements.get('stage3-preview-summary').textContent, /3 sessions · 3 h/);
  const rows = JSON.parse(h.run(`JSON.stringify(stage3Preview.rows.map(row => ({
    weekStart: row.weekStart, day: row.day, groupId: row.groupId, block: row.block
  })))`));
  assert.equal(new Set(rows.map(row => row.groupId)).size, 3);
  assert.ok(rows.every(row => row.block.assignment_id === 'hw-essay' && row.block.kind === 'flexible'
    && row.block.start === null && !('pomodoro_parent_id' in row.block)));

  let changes;
  h.handle(async (path, options) => {
    if (path.startsWith('/api/week?')) return response(200, { week_start: weekOf(path), blocks: [], revision: 0 });
    assert.equal(path, '/api/changes');
    changes = JSON.parse(options.body);
    return response(200, changesReply(changes));
  });
  assert.equal(await h.run('confirmStage3Preview()'), true);
  assert.equal(changes.weeks.length, 2);
  assert.equal(changes.weeks.flatMap(week => week.blocks).length, 3);
  assert.equal(new Set(changes.weeks.flatMap(week => week.blocks).map(block => block.id)).size, 3);
  assert.ok(changes.weeks.flatMap(week => week.blocks).every(block => block.assignment_id === 'hw-essay'));
  assert.equal(h.run('undoSteps.length'), 1);
});

test('a failed spread confirmation retries one operation without changing weeks early', async () => {
  const h = harness();
  const item = assignment({ due: '2026-09-16T21:00', unplanned_min: 60 });
  await h.login({ owned: [item] });
  h.run("openSpreadDialog('hw-essay')");
  h.handle(async path => {
    assert.equal(path, '/api/assignments/hw-essay/spread');
    return response(200, { assignment_id: 'hw-essay', session_min: 60, remaining_min: 0,
      sessions: [{ week_start: MONDAY, date: '2026-09-10', days: [3], duration_min: 60 }] });
  });
  assert.equal(await h.run('previewSpread()'), true);
  const operations = [];
  let attempt = 0;
  h.handle(async (path, options) => {
    assert.equal(path, '/api/changes');
    const body = JSON.parse(options.body);
    operations.push(body.operation_id);
    attempt += 1;
    return attempt === 1 ? response(503, { detail: 'Try again' }) : response(200, changesReply(body));
  });
  assert.equal(await h.run('confirmStage3Preview()'), false);
  assert.equal(h.run(`weekState('${MONDAY}').blocks.length`), 0);
  assert.equal(await h.run('confirmStage3Preview()'), true);
  assert.equal(new Set(operations).size, 1);
  assert.equal(h.run(`weekState('${MONDAY}').blocks.length`), 1);
  assert.equal(h.run('undoSteps.length'), 1);
});

test('spread keeps sub-slot minutes visible instead of dropping them', async () => {
  const h = harness();
  const item = assignment({ due: '2026-09-16T21:00', estimate_min: 67, unplanned_min: 67 });
  await h.login({ owned: [item] });
  h.run("openSpreadDialog('hw-essay')");
  h.handle(async path => {
    assert.equal(path, '/api/assignments/hw-essay/spread');
    return response(200, { assignment_id: 'hw-essay', session_min: 60, remaining_min: 7,
      sessions: [{ week_start: MONDAY, date: '2026-09-10', days: [3], duration_min: 60 }] });
  });
  assert.equal(await h.run('previewSpread()'), true);
  assert.match(h.elements.get('stage3-preview-summary').textContent, /7 minutes cannot fit/);
  assert.match(h.elements.get('stage3-preview-summary').textContent, /not been dropped/);
});

test('spread blocks confirmation before a destination would exceed 100 blocks', async () => {
  const h = harness();
  const blocks = Array.from({ length: 100 }, (_, index) => fixed({ id: 'fixed-' + index }));
  const item = assignment({ due: '2026-09-16T21:00', unplanned_min: 60 });
  await h.login({ blocks, owned: [item] });
  h.run("openSpreadDialog('hw-essay')");
  h.handle(async path => {
    assert.equal(path, '/api/assignments/hw-essay/spread');
    return response(200, { assignment_id: 'hw-essay', session_min: 60, remaining_min: 0,
      sessions: [{ week_start: MONDAY, date: '2026-09-10', days: [3], duration_min: 60 }] });
  });
  assert.equal(await h.run('previewSpread()'), true);
  assert.equal(h.elements.get('stage3-preview-confirm').disabled, true);
  assert.match(h.elements.get('stage3-preview-error').textContent, /exceed 100 blocks/);
});

test('priority and energy labels stay readable without changing stored values', () => {
  assert.match(html, /<option value="1">Tests first<\/option>/);
  assert.match(html, /<option value="2">Quizzes next<\/option>/);
  assert.match(html, /<option value="3" selected>Homework<\/option>/);
  assert.match(html, /<option value="4">Reading if there is time<\/option>/);
  assert.match(html, /<option value="high">High energy, mornings<\/option>/);
  assert.match(html, /<option value="medium" selected>Typical energy, afternoons<\/option>/);
  assert.match(html, /<option value="low">Low energy, evenings<\/option>/);
  const h = harness();
  assert.equal(h.run('PRIORITY_LABEL[1]'), 'tests first');
  assert.equal(h.run('PRIORITY_LABEL[2]'), 'quizzes next');
  assert.equal(h.run('PRIORITY_LABEL[4]'), 'reading last');
  assert.equal(h.run("ENERGY_LABEL.high"), 'morning energy');
  assert.equal(h.run("ENERGY_LABEL.low"), 'evening energy');
  assert.equal(h.run("ENERGY_LABEL.medium"), 'afternoon energy');
});

test('deadline-cluster advice stays visible and does not claim the week was solved', async () => {
  const h = harness();
  await h.login({ blocks: [sessionBlock(), sessionBlock({ id: 'lab', title: 'Lab' })] });
  const message = 'Several tasks are short on time. Shorten a session, pick another day, '
    + 'or free some protected hours. Work that cannot fit stays unplaced.';
  h.run(`showTrace(${JSON.stringify({
    placed: [],
    unplaced: [
      { id: 'session', title: 'Essay', kind: 'flexible', duration_min: 120, days: [0] },
      { id: 'lab', title: 'Lab', kind: 'flexible', duration_min: 120, days: [0] },
    ],
    moves: [],
    explanations: [
      { block_id: 'session', reason: 'NO_SLOT_LEFT', message: 'No slot left' },
      { block_id: 'session', reason: null, message },
    ],
    failed_constraints: ['NO_SLOT_LEFT'],
    solve_ms: 1,
    complete: false,
  })})`);
  const open = h.elements.get('debug-unplaced').children.map(item => item.textContent).join('\n');
  assert.match(open, /Several tasks are short on time/);
  assert.match(open, /Work that cannot fit stays unplaced/);
  assert.doesNotMatch(open, /See the rest of your plan/);
  assert.equal(h.elements.get('debug-unplaced').querySelector('.cluster-advice').textContent, message);
});
