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
const same = (actual, expected) => assert.equal(JSON.stringify(actual), JSON.stringify(expected));

class FixedDate extends Date {
  constructor(...args) {
    if (args.length === 0) super(NOW.getTime());
    else super(...args);
  }
  static now() { return NOW.getTime(); }
}

function harness() {
  const elements = new Map();
  const allElements = [];
  function connectedElements() {
    const found = [];
    const seen = new Set();
    function visit(el) {
      if (seen.has(el)) return;
      seen.add(el);
      found.push(el);
      el.children.forEach(visit);
    }
    elements.forEach(visit);
    return found;
  }
  function element() {
    const classes = new Set();
    const el = {
      value: '', textContent: '', hidden: false, disabled: false, dataset: {}, style: {},
      children: [], listeners: {},
      get className() { return Array.from(classes).join(' '); },
      set className(value) {
        classes.clear();
        String(value).split(/\s+/).filter(Boolean).forEach(name => classes.add(name));
      },
      classList: {
        add: name => classes.add(name),
        remove: name => classes.delete(name),
        contains: name => classes.has(name),
      },
      set innerHTML(value) { this.children = []; },
      get innerHTML() { return ''; },
      addEventListener(name, handler) { this.listeners[name] = handler; },
      appendChild(child) { this.children.push(child); },
      replaceChildren() { this.children = []; },
      querySelector(sel) {
        return this.children.find(child =>
          sel.split(',').some(part => child.classList.contains(part.trim().replace(/^\./, ''))),
        ) || null;
      },
      querySelectorAll() { return []; },
      closest() { return null; },
      getBoundingClientRect() {
        return { top: 0, bottom: 100, left: 0, right: 100, height: 100, width: 100 };
      },
      setPointerCapture() {}, releasePointerCapture() {},
      reset() {}, focus() {}, click() {}, scrollIntoView() {},
      contains(node) { return this === node || this.children.includes(node); },
    };
    allElements.push(el);
    return el;
  }
  for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], element());
  const local = new Map();
  let handler = async () => response(401, { detail: 'Please sign in' });
  const requests = [];
  const context = vm.createContext({
    document: {
      getElementById: id => {
        assert.ok(elements.has(id), `Missing HTML element ${id}`);
        return elements.get(id);
      },
      documentElement: { dataset: { theme: 'nocturne' } },
      createElement: element, addEventListener() {},
      querySelectorAll: selector => connectedElements().filter(el =>
        selector.split(',').some(part => el.classList.contains(part.trim().replace(/^\./, '')))),
    },
    window: { addEventListener() {} },
    localStorage: { getItem: key => local.get(key), removeItem: key => local.delete(key) },
    fetch: async (path, options) => { requests.push({ path, options }); return handler(path, options); },
    getComputedStyle: () => ({ getPropertyValue: () => '2.75rem' }),
    setTimeout, clearTimeout, AbortController, structuredClone, console,
    confirm: () => true, Date: FixedDate,
  });
  runAppScripts(vm, context);
  return {
    elements, requests, allElements,
    run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    async login(id = 1, blocks = [], saved = []) {
      await tick();
      handler = async path => {
        if (path.startsWith('/api/weeks')) return response(200, { weeks: saved });
        if (path.startsWith('/api/week')) {
          return response(200, { week_start: weekOf(path), blocks, revision: 0 });
        }
        return response(200, { theme: 'nocturne' });
      };
      await vm.runInContext(`loadAccount({id:${id},username:'student${id}'})`, context);
    },
  };
}

test('snapMinute rounds to 15 and clamps to 06:00–23:00', () => {
  const h = harness();
  assert.equal(h.run('snapMinute(367)'), 360);
  assert.equal(h.run('snapMinute(368)'), 375);
  assert.equal(h.run('snapMinute(0)'), 360);
  assert.equal(h.run('snapMinute(2000)'), 1380);
  assert.equal(h.run('formatMinute(375)'), '06:15');
});

test('createDragRange and createClickRange follow Daily Scheduler rules at 15 min', () => {
  const h = harness();
  same(h.run('createDragRange(360, 400)'), { startMin: 360, endMin: 405 });
  same(h.run('createDragRange(400, 360)'), { startMin: 360, endMin: 405 });
  same(h.run('createClickRange(900, [{startMin:930,endMin:960}])'), { startMin: 900, endMin: 930 });
  same(h.run('createClickRange(900, [])'), { startMin: 900, endMin: 960 });
  assert.equal(h.run('createClickRange(1365, [{startMin:1370,endMin:1380}])'), null);
});

test('moveRange and resize ranges keep min duration and day bounds', () => {
  const h = harness();
  same(h.run('moveRange(600, 660, 20)'), { startMin: 615, endMin: 675 });
  same(h.run('moveRange(360, 420, -60)'), { startMin: 360, endMin: 420 });
  same(h.run('moveRange(1300, 1360, 60)'), { startMin: 1320, endMin: 1380 });
  same(h.run('resizeTopRange(600, 660, 50)'), { startMin: 645, endMin: 660 });
  same(h.run('resizeTopRange(600, 660, 200)'), { startMin: 645, endMin: 660 });
  same(h.run('resizeBottomRange(600, 660, -50)'), { startMin: 600, endMin: 615 });
  same(h.run('resizeBottomRange(1320, 1365, 60)'), { startMin: 1320, endMin: 1380 });
});

const chip = (h, container, category) =>
  h.elements.get(container).children.find(button => button.dataset.category === category);
const submitEditor = h => h.elements.get('block-form').listeners.submit({ preventDefault() {} });

test('dragging empty grid opens the editor on that range and adds nothing until Save', async () => {
  const h = harness();
  await h.login();
  const bodies = [];
  h.handle(async (path, options) => {
    assert.equal(path, '/api/week');
    const payload = JSON.parse(options.body);
    bodies.push(payload);
    return response(200, { week_start: MONDAY, blocks: payload.blocks, revision: bodies.length });
  });
  chip(h, 'type-chips', 'exercise').listeners.click();

  assert.equal(h.run('requestCreate(1, 960, 1020)'), true);
  assert.equal(h.elements.get('block-dialog').open, true);
  assert.equal(h.elements.get('f-when-day').value, '1');
  assert.equal(h.elements.get('f-start').value, '16:00');
  assert.equal(h.elements.get('f-end').value, '17:00');
  assert.equal(h.elements.get('f-kind-locked').checked, true);
  assert.equal(h.run('weekState().blocks.length'), 0);
  await tick();
  assert.equal(bodies.length, 0);

  h.elements.get('f-title').value = 'Soccer practice';
  assert.equal(submitEditor(h), true);
  await tick();
  assert.equal(h.elements.get('block-dialog').open, false);
  same(h.run('weekState().blocks.map(b => [b.title, b.kind, b.category, b.days, b.start, b.duration_min])'),
    [['Soccer practice', 'locked', 'exercise', [1], '16:00', 60]]);
  assert.equal(bodies.length, 1);
  assert.equal(bodies[0].blocks[0].title, 'Soccer practice');
});

test('clicking empty grid offers a 1-hour block clipped at the next block, titled by its type', async () => {
  const h = harness();
  const busy = { id: 'busy', kind: 'locked', title: 'Busy', duration_min: 30, days: [0], start: '15:30', priority: 3, energy: 'medium' };
  await h.login(1, [busy]);
  h.handle(async (_path, options) => response(200, { week_start: MONDAY, blocks: JSON.parse(options.body).blocks, revision: 1 }));
  chip(h, 'type-chips', 'meals').listeners.click();

  assert.equal(h.run('requestCreateAt(1, 900)'), true);
  assert.equal(h.elements.get('f-start').value, '15:00');
  assert.equal(h.elements.get('f-end').value, '16:00');
  h.elements.get('form-cancel').listeners.click();
  assert.equal(h.run('weekState().blocks.length'), 1);

  h.run('requestCreateAt(0, 900)');
  assert.equal(h.elements.get('f-end').value, '15:30');
  submitEditor(h);
  await tick();
  same(h.run('weekState().blocks.find(b => b.id !== "busy")').title, 'Meals');
  same(h.run('weekState().blocks.find(b => b.id !== "busy").duration_min'), 30);
});

test('a flexible type dragged on a day becomes a task Solve may place on that day', async () => {
  const h = harness();
  await h.login();
  h.handle(async (_path, options) => response(200, { week_start: MONDAY, blocks: JSON.parse(options.body).blocks, revision: 1 }));
  chip(h, 'type-chips', 'assignments').listeners.click();

  h.run('requestCreate(2, 960, 1050)');
  assert.equal(h.elements.get('f-kind-flexible').checked, true);
  assert.equal(h.elements.get('f-duration').value, '90');
  assert.equal(h.elements.get('f-flex-summary').textContent,
    'Solve will find 1 h 30 min for it on Wednesday. It has no due time.');
  h.elements.get('f-title').value = 'Chemistry lab report';
  submitEditor(h);
  await tick();
  same(h.run('weekState().blocks.map(b => [b.kind, b.days, b.start, b.duration_min, b.latest, b.category])'),
    [['flexible', [2], null, 90, null, 'assignments']]);
});

test('the editor refuses a task with no days, and says so, instead of saving', async () => {
  const h = harness();
  await h.login();
  let puts = 0;
  h.handle(async () => { puts += 1; return response(200, { week_start: MONDAY, blocks: [], revision: 1 }); });
  chip(h, 'type-chips', 'assignments').listeners.click();
  h.elements.get('add-block').listeners.click();
  for (let day = 0; day < 7; day += 1) h.elements.get(`f-day-${day}`).checked = false;

  assert.equal(submitEditor(h), false);
  await tick();
  assert.equal(puts, 0);
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(h.elements.get('block-dialog').open, true);
  assert.equal(h.elements.get('form-error').hidden, false);
  assert.equal(h.elements.get('form-error').textContent, 'Pick at least one day FlexWeek can use for it.');
});

test('a due day before every allowed day is an error that names both', async () => {
  const h = harness();
  await h.login();
  h.run('requestCreate(4, 960, 1020)');
  h.elements.get('f-due-day').value = '1';
  assert.equal(submitEditor(h), false);
  assert.equal(h.elements.get('form-error').textContent,
    'It is due Tuesday, but every day you picked comes after that. Pick an earlier day or a later due day.');
  assert.equal(h.run('weekState().blocks.length'), 0);
});

test('Add without dragging starts from the type preset, not a blank 16:00 block', async () => {
  const h = harness();
  await h.login();
  h.handle(async (_path, options) => response(200, { week_start: MONDAY, blocks: JSON.parse(options.body).blocks, revision: 1 }));

  chip(h, 'type-chips', 'class').listeners.click();
  h.elements.get('add-block').listeners.click();
  assert.equal(h.elements.get('f-start').value, '08:00');
  assert.equal(h.elements.get('f-end').value, '14:30');
  same([0, 1, 2, 3, 4, 5, 6].map(day => h.elements.get(`f-day-${day}`).checked),
    [true, true, true, true, true, false, false]);
  submitEditor(h);
  await tick();
  same(h.run('weekState().blocks.map(b => [b.title, b.days, b.start, b.duration_min])'),
    [['School', [0, 1, 2, 3, 4], '08:00', 390]]);

  chip(h, 'type-chips', 'assignments').listeners.click();
  h.elements.get('add-block').listeners.click();
  assert.equal(h.elements.get('f-duration').value, '60');
  h.elements.get('f-due-day').value = '2';
  h.elements.get('f-due-day').listeners.change();
  same([0, 1, 2, 3, 4, 5, 6].map(day => h.elements.get(`f-day-${day}`).checked),
    [true, true, true, false, false, false, false]);
  assert.equal(h.elements.get('f-flex-summary').textContent,
    'Solve will find 1 h for it on Monday, Tuesday or Wednesday. It is due Wednesday at 21:00.');
});

test('move and resize update start/duration and keep 15-min grid', async () => {
  const h = harness();
  const school = {
    id: 'school', kind: 'locked', title: 'School', duration_min: 60,
    days: [0], start: '10:00', priority: 1, energy: 'medium',
  };
  await h.login(1, [school]);
  h.handle(async (_path, options) => {
    const payload = JSON.parse(options.body);
    return response(200, { week_start: MONDAY, blocks: payload.blocks, revision: 1 });
  });

  assert.equal(h.run('applyBlockTimes("school", 630, 705)'), true);
  await tick();
  assert.equal(h.run('weekState().blocks[0].start'), '10:30');
  assert.equal(h.run('weekState().blocks[0].duration_min'), 75);

  same(h.run('moveRange(630, 705, -40)'), { startMin: 585, endMin: 660 });
  assert.equal(h.run('applyBlockTimes("school", 585, 660)'), true);
  await tick();
  assert.equal(h.run('weekState().blocks[0].start'), '09:45');
  assert.equal(h.run('weekState().blocks[0].duration_min'), 75);
});

test('categoryColor maps thin palette and the chosen type persists as the category', async () => {
  const h = harness();
  assert.equal(h.run('categoryColor("class")'), '#3b82f6');
  assert.equal(h.run('categoryColor("nope")'), null);
  await h.login();
  let savedCategory = null;
  h.handle(async (_path, options) => {
    const payload = JSON.parse(options.body);
    savedCategory = payload.blocks[0].category;
    return response(200, { week_start: MONDAY, blocks: payload.blocks, revision: 1 });
  });
  h.run('requestCreate(2, 720, 780)');
  chip(h, 'category-chips', 'meals').listeners.click();
  submitEditor(h);
  await tick();
  assert.equal(savedCategory, 'meals');
  assert.equal(h.run('weekState().blocks[0].category'), 'meals');
  assert.equal(h.run('weekState().blocks[0].kind'), 'locked');
});

test('dragging one day of a repeating locked block is refused, not applied to the series', async () => {
  const h = harness();
  const school = {
    id: 'school', kind: 'locked', title: 'School', duration_min: 60,
    days: [0, 1, 2], start: '10:00', priority: 1, energy: 'medium',
  };
  await h.login(1, [school]);
  let putCount = 0;
  h.handle(async (_path, options) => {
    putCount += 1;
    return response(200, { week_start: MONDAY, blocks: JSON.parse(options.body).blocks, revision: 1 });
  });

  assert.equal(h.run('applyBlockTimes("school", 630, 705)'), false);
  await tick();
  assert.equal(putCount, 0);
  assert.equal(h.run('weekState().blocks[0].start'), '10:00');
  assert.equal(h.run('weekState().blocks[0].duration_min'), 60);
  same(h.run('weekState().blocks[0].days'), [0, 1, 2]);
});

test('a one-day occurrence split off a series can still be dragged', async () => {
  const h = harness();
  const single = {
    id: 'occ-1-school', kind: 'locked', title: 'School', duration_min: 60,
    days: [1], start: '10:00', priority: 1, energy: 'medium',
  };
  await h.login(1, [single]);
  h.handle(async (_path, options) =>
    response(200, { week_start: MONDAY, blocks: JSON.parse(options.body).blocks, revision: 1 }));

  assert.equal(h.run('applyBlockTimes("occ-1-school", 630, 705)'), true);
  await tick();
  assert.equal(h.run('weekState().blocks[0].start'), '10:30');
  assert.equal(h.run('weekState().blocks[0].duration_min'), 75);
});

test('a flexible task with several candidate days still drags: series is a locked idea', async () => {
  const h = harness();
  // Candidate days, not repeated events. The context menu only offers occurrence
  // and series actions for locked blocks, so refusing this drag would strand it.
  const essay = {
    id: 'essay', kind: 'flexible', title: 'Essay', duration_min: 60,
    days: [1, 3], start: '10:00', priority: 3, energy: 'medium',
  };
  await h.login(1, [essay]);
  h.handle(async (_path, options) =>
    response(200, { week_start: MONDAY, blocks: JSON.parse(options.body).blocks, revision: 1 }));

  assert.equal(h.run('applyBlockTimes("essay", 630, 690)'), true);
  await tick();
  assert.equal(h.run('weekState().blocks[0].start'), '10:30');
  same(h.run('weekState().blocks[0].days'), [1, 3]);
});
