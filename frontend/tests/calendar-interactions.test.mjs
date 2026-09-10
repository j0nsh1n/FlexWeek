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

test('drag create and click create persist locked blocks through saveWeek', async () => {
  const h = harness();
  await h.login();
  const bodies = [];
  h.handle(async (path, options) => {
    assert.equal(path, '/api/week');
    const payload = JSON.parse(options.body);
    bodies.push(payload);
    return response(200, { week_start: MONDAY, blocks: payload.blocks, revision: bodies.length });
  });

  const created = JSON.parse(h.run('JSON.stringify(applyCreateLocked(1, 960, 1020))'));
  assert.equal(created.kind, 'locked');
  assert.equal(created.start, '16:00');
  assert.equal(created.duration_min, 60);
  assert.equal(h.run('weekState().blocks.length'), 1);
  assert.equal(h.run('weekState().blocks[0].days[0]'), 1);
  await tick();
  assert.ok(bodies.length >= 1);

  h.run('weekState().blocks = []');
  h.run('applyCreateClick(0, 900)');
  await tick();
  assert.equal(h.run('weekState().blocks[0].start'), '15:00');
  assert.equal(h.run('weekState().blocks[0].duration_min'), 60);

  h.run('weekState().blocks = [{id:"busy",kind:"locked",title:"Busy",duration_min:30,days:[0],start:"15:30",priority:3,energy:"medium"}]');
  h.run('applyCreateClick(0, 900)');
  await tick();
  assert.equal(h.run('weekState().blocks.length'), 2);
  assert.equal(h.run('weekState().blocks.find(function (b) { return b.title === "New block"; }).duration_min'), 30);
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

test('categoryColor maps thin palette and optional category persists', async () => {
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
  h.run('applyCreateLocked(2, 720, 780)');
  await tick();
  h.run('weekState().blocks[0].category = "study"');
  assert.equal(await h.run('saveWeek()'), true);
  assert.equal(savedCategory, 'study');
  assert.equal(h.run('weekState().blocks[0].category'), 'study');
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
