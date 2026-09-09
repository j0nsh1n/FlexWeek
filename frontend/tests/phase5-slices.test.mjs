process.env.TZ = 'America/Los_Angeles';

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
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
      value: '', textContent: '', hidden: false, disabled: false, checked: false, dataset: {}, style: {},
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
      showModal() { this.open = true; },
      close() { this.open = false; },
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
      hidden: false,
    },
    window: { addEventListener() {}, AudioContext: undefined },
    localStorage: { getItem: key => local.get(key), removeItem: key => local.delete(key) },
    fetch: async (path, options) => { requests.push({ path, options }); return handler(path, options); },
    getComputedStyle: () => ({ getPropertyValue: () => '2.75rem' }),
    setTimeout, clearTimeout, setInterval, clearInterval, AbortController, structuredClone, console,
    confirm: () => true, Date: FixedDate, Notification: undefined, URL, Blob,
  });
  vm.runInContext(source, context);
  return {
    elements, requests, allElements,
    run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    async login(id = 1, blocks = [], saved = [], preferences = null) {
      await tick();
      const prefs = preferences || {
        theme: 'nocturne', reminders_enabled: false, reminder_lead_min: 5, reminder_sound: true,
      };
      handler = async path => {
        if (path.startsWith('/api/weeks')) return response(200, { weeks: saved });
        if (path.startsWith('/api/week')) {
          return response(200, { week_start: weekOf(path), blocks, revision: 0 });
        }
        return response(200, prefs);
      };
      await vm.runInContext(`loadAccount({id:${id},username:'student${id}'})`, context);
    },
  };
}

test('D: removeOccurrence and editOccurrence split series vs one day', () => {
  const h = harness();
  const series = {
    id: 'school', kind: 'locked', title: 'School', duration_min: 60,
    days: [0, 1, 2, 3, 4], start: '08:00', priority: 1, energy: 'medium', missed_days: [1],
  };
  same(h.run(`removeOccurrence(${JSON.stringify(series)}, 1)`).days, [0, 2, 3, 4]);
  assert.equal(h.run(`removeOccurrence(${JSON.stringify(series)}, 1)`).missed_days.length, 0);
  assert.equal(h.run(`removeOccurrence({id:'x',days:[2],kind:'locked'}, 2)`), null);

  const edited = h.run(`editOccurrence(${JSON.stringify(series)}, 2, {start:'09:00',duration_min:45,title:'Late school'})`);
  same(edited.series.days, [0, 1, 3, 4]);
  assert.equal(edited.split.days[0], 2);
  assert.equal(edited.split.start, '09:00');
  assert.equal(edited.split.duration_min, 45);
  assert.equal(edited.split.title, 'Late school');
  assert.notEqual(edited.split.id, 'school');

  const seriesEdit = h.run(`editSeries(${JSON.stringify(series)}, {start:'08:30',title:'School day'})`);
  same(seriesEdit.days, [0, 1, 2, 3, 4]);
  assert.equal(seriesEdit.start, '08:30');
  assert.equal(seriesEdit.title, 'School day');
});

test('D: deleteOccurrenceById keeps other weekdays of the series', async () => {
  const h = harness();
  const school = {
    id: 'school', kind: 'locked', title: 'School', duration_min: 60,
    days: [0, 1, 2], start: '08:00', priority: 1, energy: 'medium',
  };
  await h.login(1, [school]);
  h.handle(async (_path, options) => {
    const payload = JSON.parse(options.body);
    return response(200, { week_start: MONDAY, blocks: payload.blocks, revision: 1 });
  });
  assert.equal(h.run('deleteOccurrenceById("school", 1)'), true);
  await tick();
  same(h.run('weekState().blocks[0].days'), [0, 2]);
  assert.equal(h.run('weekState().blocks.length'), 1);
});

test('F: startAlertDue matches Daily Scheduler lead window math', () => {
  const h = harness();
  // Fires when fire_at is in [now - window, now] (just reached / slightly late).
  assert.equal(h.run('startAlertDue(600, 600, 0, 2)'), true);
  assert.equal(h.run('startAlertDue(600, 602, 0, 2)'), true);
  assert.equal(h.run('startAlertDue(600, 603, 0, 2)'), false);
  assert.equal(h.run('startAlertDue(600, 598, 0, 2)'), false);
  assert.equal(h.run('startAlertDue(600, 590, 10, 2)'), true);
  assert.equal(h.run('startAlertDue(600, 593, 10, 2)'), false);
  assert.equal(h.run('startAlertDue(5, 0, 15, 2)'), true);
});

test('F: reminder preference payload persists through save', async () => {
  const h = harness();
  await h.login();
  let saved = null;
  h.handle(async (path, options) => {
    assert.equal(path, '/api/preferences');
    saved = JSON.parse(options.body);
    return response(200, saved);
  });
  h.run('prefs.reminders_enabled = true; prefs.reminder_lead_min = 15; prefs.reminder_sound = false;');
  assert.equal(await h.run('api("/api/preferences", { method: "PUT", body: JSON.stringify(preferencesPayload()) }).then(r => { applyPreferences(r); return true; })'), true);
  assert.equal(saved.reminders_enabled, true);
  assert.equal(saved.reminder_lead_min, 15);
  assert.equal(saved.reminder_sound, false);
  assert.equal(h.run('prefs.reminder_lead_min'), 15);
});

test('B: category chips palette includes sleep and colors map', () => {
  const h = harness();
  assert.equal(h.run('categoryColor("sleep")'), '#6366f1');
  assert.equal(h.run('categoryLabel("assignments")'), 'Homework');
  assert.ok(h.run('CATEGORIES.some(function (c) { return c.id === "class"; })'));
  assert.ok(h.run('CATEGORIES.some(function (c) { return c.id === "sleep"; })'));
});

test('B: category on create/edit persists through week save', async () => {
  const h = harness();
  await h.login();
  let savedCategory = null;
  h.handle(async (_path, options) => {
    const payload = JSON.parse(options.body);
    savedCategory = payload.blocks[0].category;
    return response(200, { week_start: MONDAY, blocks: payload.blocks, revision: 1 });
  });
  h.run('applyCreateLocked(0, 720, 780)');
  await tick();
  h.run('weekState().blocks[0].category = "class"');
  assert.equal(await h.run('saveWeek()'), true);
  assert.equal(savedCategory, 'class');
});

test('E: export/import week JSON round-trips without wiping other weeks', async () => {
  const h = harness();
  const blocks = [{
    id: 'school', kind: 'locked', title: 'School', duration_min: 60,
    days: [0, 1], start: '08:00', priority: 1, energy: 'medium', completed: true, category: 'class',
  }];
  await h.login(1, blocks, [MONDAY, '2026-08-31']);
  const payload = h.run(`exportWeekPayload("${MONDAY}", weekState().blocks)`);
  assert.equal(payload.format, 'flexweek-week');
  assert.equal(payload.blocks[0].completed, true);
  const text = h.run(`formatWeekExportText("${MONDAY}", weekState().blocks)`);
  assert.match(text, /School/);
  assert.match(text, /\[done\]/);

  const parsed = h.run(`parseImportPayload(${JSON.stringify(JSON.stringify(payload))})`);
  assert.equal(parsed.error, undefined);
  assert.equal(parsed.week_start, MONDAY);

  let putCount = 0;
  h.handle(async (path, options) => {
    if (path === '/api/week') {
      putCount += 1;
      const body = JSON.parse(options.body);
      assert.equal(body.week_start, MONDAY);
      return response(200, { week_start: MONDAY, blocks: body.blocks, revision: putCount });
    }
    if (path.startsWith('/api/week?')) {
      return response(200, { week_start: weekOf(path), blocks: [], revision: 0 });
    }
    return response(200, { weeks: [MONDAY, '2026-08-31'] });
  });
  assert.equal(await h.run(`importPayloadIntoWeek(${JSON.stringify(parsed)}, "replace")`), true);
  await tick();
  assert.equal(h.run('weekState().blocks[0].id'), 'school');
  assert.equal(h.run('savedWeeks.includes("2026-08-31")'), true);
});

test('E: completed flag toggles and survives saveWeek', async () => {
  const h = harness();
  const task = {
    id: 'hw', kind: 'flexible', title: 'Essay', duration_min: 60, days: [0],
    priority: 3, energy: 'medium', completed: false,
  };
  await h.login(1, [task]);
  let saved = null;
  h.handle(async (_path, options) => {
    saved = JSON.parse(options.body).blocks[0];
    return response(200, { week_start: MONDAY, blocks: [saved], revision: 1 });
  });
  assert.equal(h.run('toggleCompleted("hw")'), true);
  await tick();
  assert.equal(saved.completed, true);
  assert.equal(h.run('weekState().blocks[0].completed'), true);
});

test('E: import aborts without mutating or saving the current week when the switch fails', async () => {
  const h = harness();
  const homework = {
    id: 'hw', kind: 'flexible', title: 'Essay', duration_min: 60, days: [0],
    priority: 3, energy: 'medium',
  };
  await h.login(1, [homework], [MONDAY]);
  const payload = {
    format: 'flexweek-week', version: 1, week_start: '2026-08-31',
    blocks: [{ id: 'other', kind: 'locked', title: 'Other week', duration_min: 30, days: [0], start: '09:00' }],
  };
  const parsed = h.run(`parseImportPayload(${JSON.stringify(JSON.stringify(payload))})`);
  assert.equal(parsed.error, undefined);

  let putCount = 0;
  h.handle(async (path, options) => {
    if (path === '/api/week') {
      putCount += 1;
      return response(200, { week_start: MONDAY, blocks: JSON.parse(options.body).blocks, revision: 1 });
    }
    if (path.startsWith('/api/week?')) return response(500, { detail: 'Server down' });
    return response(200, { weeks: [MONDAY] });
  });
  assert.equal(await h.run(`importPayloadIntoWeek(${JSON.stringify(parsed)})`), false);
  await tick();
  assert.equal(putCount, 0);
  assert.equal(h.run('selectedWeek'), MONDAY);
  same(h.run('weekState().blocks'), [homework]);
});

test('E: day import updates one occurrence and keeps the rest of the series', async () => {
  const h = harness();
  const school = {
    id: 'school', kind: 'locked', title: 'School', duration_min: 60,
    days: [1, 2], start: '08:00', priority: 1, energy: 'medium', missed_days: [1],
  };
  const sport = {
    id: 'sport', kind: 'locked', title: 'Soccer', duration_min: 90,
    days: [4], start: '16:00', priority: 1, energy: 'high',
  };
  await h.login(1, [school, sport]);
  const payload = h.run(`exportDayPayload("${MONDAY}", 2, weekState().blocks)`);
  assert.equal(payload.format, 'flexweek-day');
  same(payload.blocks.map(b => b.days), [[2]]);

  const parsed = h.run(`parseImportPayload(${JSON.stringify(JSON.stringify(payload))})`);
  assert.equal(parsed.error, undefined);

  let putBlocks = null;
  h.handle(async (_path, options) => {
    putBlocks = JSON.parse(options.body).blocks;
    return response(200, { week_start: MONDAY, blocks: putBlocks, revision: 1 });
  });
  assert.equal(await h.run(`importPayloadIntoWeek(${JSON.stringify(parsed)})`), true);
  await tick();
  assert.equal(putBlocks.length, 3);
  const series = putBlocks.find(b => b.id === 'school');
  same(series.days, [1]);
  same(series.missed_days, [1]);
  assert.equal(series.start, '08:00');
  const wednesday = putBlocks.find(b => b.id === 'occ-2-school');
  assert.ok(wednesday, 'Wednesday occurrence kept as its own block');
  same(wednesday.days, [2]);
  assert.equal(wednesday.title, 'School');
  assert.equal(wednesday.start, '08:00');
  same(putBlocks.find(b => b.id === 'sport').days, [4]);

  assert.equal(await h.run(`importPayloadIntoWeek(${JSON.stringify(parsed)})`), true);
  await tick();
  assert.equal(putBlocks.length, 3);
  same(putBlocks.find(b => b.id === 'school').days, [1]);
  same(putBlocks.find(b => b.id === 'occ-2-school').days, [2]);
});

test('E: a malformed import is refused before the week is touched or saved', async () => {
  const h = harness();
  const homework = {
    id: 'hw', kind: 'flexible', title: 'Essay', duration_min: 60, days: [0],
    priority: 3, energy: 'medium',
  };
  await h.login(1, [homework], [MONDAY]);
  let putCount = 0;
  h.handle(async (path, options) => {
    if (path === '/api/week') {
      putCount += 1;
      return response(200, { week_start: MONDAY, blocks: JSON.parse(options.body).blocks, revision: 1 });
    }
    return response(200, { weeks: [MONDAY] });
  });

  const bad = {
    'a duration off the 15-minute grid': { duration_min: 10 },
    'a weekday outside 0..6': { days: [9] },
    'a locked block with no start': { start: undefined },
    'a start that runs past 23:00': { start: '22:30', duration_min: 120 },
    'missed days on a flexible task': { kind: 'flexible', missed_days: [0] },
  };
  for (const [why, patch] of Object.entries(bad)) {
    const block = Object.assign(
      { id: 'x', kind: 'locked', title: 'Bad', duration_min: 60, days: [0], start: '09:00' },
      patch,
    );
    if (patch.start === undefined && 'start' in patch) delete block.start;
    const payload = { format: 'flexweek-week', version: 1, week_start: MONDAY, blocks: [block] };
    const parsed = h.run(`parseImportPayload(${JSON.stringify(JSON.stringify(payload))})`);
    assert.ok(parsed.error, `expected ${why} to be refused`);
    assert.equal(await h.run(`importPayloadIntoWeek(${JSON.stringify(parsed)})`), false);
  }

  await tick();
  assert.equal(putCount, 0);
  same(h.run('weekState().blocks'), [homework]);
});

test('E: an export from a newer FlexWeek is refused rather than half-read', async () => {
  const h = harness();
  const homework = {
    id: 'hw', kind: 'flexible', title: 'Essay', duration_min: 60, days: [0],
    priority: 3, energy: 'medium',
  };
  await h.login(1, [homework], [MONDAY]);
  let putCount = 0;
  h.handle(async (path, options) => {
    if (path === '/api/week') {
      putCount += 1;
      return response(200, { week_start: MONDAY, blocks: JSON.parse(options.body).blocks, revision: 1 });
    }
    return response(200, { weeks: [MONDAY] });
  });

  const future = {
    format: 'flexweek-week', version: 99, week_start: MONDAY,
    blocks: [{ id: 'n', kind: 'locked', title: 'New', duration_min: 60, days: [0], start: '09:00' }],
  };
  const parsed = h.run(`parseImportPayload(${JSON.stringify(JSON.stringify(future))})`);
  assert.match(parsed.error, /newer FlexWeek/);
  assert.equal(await h.run(`importPayloadIntoWeek(${JSON.stringify(parsed)})`), false);

  const versionless = { format: 'flexweek-week', week_start: MONDAY, blocks: [] };
  assert.ok(h.run(`parseImportPayload(${JSON.stringify(JSON.stringify(versionless))})`).error);

  await tick();
  assert.equal(putCount, 0);
  same(h.run('weekState().blocks'), [homework]);
});
