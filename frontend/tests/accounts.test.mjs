// A week_start is a calendar label, so the date helpers must not read one as a
// UTC instant. Only a zone west of Greenwich exposes that mistake, so pin one.
process.env.TZ = 'America/Los_Angeles';

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const task = { id: 'homework', kind: 'flexible', title: 'Math', duration_min: 60, days: [0] };
const response = (status, data) => ({ status, ok: status < 400, json: async () => data });
const tick = () => new Promise(resolve => setImmediate(resolve));
const weekOf = path => new URL(path, 'http://flexweek.test').searchParams.get('week_start');
// Thursday 10 September 2026, so the week on screen starts Monday 7 September.
const NOW = new Date(2026, 8, 10, 12, 0, 0);
const MONDAY = '2026-09-07';

class FixedDate extends Date {
  constructor(...args) {
    if (args.length === 0) super(NOW.getTime());
    else super(...args);
  }
  static now() { return NOW.getTime(); }
}

function harness() {
  const elements = new Map();
  function element() {
    return {
      value: '', textContent: '', hidden: false, disabled: false, dataset: {}, style: {},
      children: [], listeners: {},
      // The app only ever assigns "", which clears a real element's children.
      set innerHTML(value) { this.children = []; },
      get innerHTML() { return ''; },
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
    confirm: () => true, Date: FixedDate,
  });
  vm.runInContext(source, context);
  return {
    elements, local, requests,
    run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    dayHeads: () => elements.get('week').children
      .filter(child => child.className === 'day-head')
      .map(head => head.children.map(part => part.textContent).join(' ')),
    async login(id = 1, blocks = [], saved = []) {
      await tick();
      handler = async path => {
        if (path.startsWith('/api/weeks')) return response(200, { week_start: saved });
        if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks, revision: 0 });
        return response(200, { theme: 'nocturne' });
      };
      await vm.runInContext(`loadAccount({id:${id},username:'student${id}'})`, context);
    },
  };
}

test('boot requires sign-in and never fetches a demo or exposes legacy data', async () => {
  const h = harness();
  h.local.set('flexweek.week.v1', JSON.stringify({ blocks: [task] }));
  await tick();
  assert.equal(h.elements.get('planner').hidden, true);
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.deepEqual(h.requests.map(r => r.path), ['/api/auth/me']);
});

test('failed save retains the draft and a retry commits the same week', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.handle(async () => { throw new Error('Offline'); });
  assert.equal(await h.run('saveWeek()'), false);
  assert.equal(h.run('weekState().dirty'), true);
  assert.equal(h.run('weekState().blocks[0].title'), 'Math');
  assert.match(h.elements.get('status').textContent, /Not saved/);
  h.handle(async (_path, options) => {
    assert.equal(options.headers['X-FlexWeek-Account'], '1');
    const payload = JSON.parse(options.body);
    assert.equal(payload.blocks[0].title, 'Math');
    assert.equal(payload.week_start, MONDAY);
    assert.equal(payload.revision, 0);
    return response(200, { week_start: MONDAY, blocks: [task], revision: 1 });
  });
  assert.equal(await h.run('saveWeek()'), true);
  assert.equal(h.run('weekState().dirty'), false);
  assert.equal(h.run('weekState().revision'), 1);
});

test('revision conflict preserves edits and prevents blind retry', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.handle(async () => response(409, { detail: 'Week changed' }));
  await h.run('saveWeek()');
  const count = h.requests.length;
  await h.run('saveWeek()');
  assert.equal(h.requests.length, count);
  assert.equal(h.run('weekState().dirty'), true);
  assert.equal(h.elements.get('retry-save').disabled, true);
  assert.equal(h.run('weekState().blocks[0].title'), 'Math');
});

test('expired session hides private data and restores unsaved edits only to the same account', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.handle(async () => response(401, { detail: 'Session expired' }));
  await h.run('saveWeek()');
  assert.equal(h.elements.get('planner').hidden, true);
  assert.equal(h.elements.get('week').children.length, 0);
  assert.equal(h.run('weekState().blocks.length'), 0);
  await h.login(1);
  assert.equal(h.run('weekState().blocks[0].title'), 'Math');
  assert.equal(h.run('weekState().dirty'), true);
  h.run('signedOut()');
  await h.login(2);
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(h.run('weekState().dirty'), false);
});

test('late save response cannot repopulate a signed-out screen', async () => {
  const h = harness();
  await h.login(1, [task]);
  let resolve;
  h.handle(() => new Promise(done => { resolve = done; }));
  const pending = h.run('saveWeek()');
  h.run('signedOut()');
  resolve(response(200, { week_start: MONDAY, blocks: [task], revision: 1 }));
  await pending;
  assert.equal(h.run('account'), null);
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(h.elements.get('planner').hidden, true);
});

test('invalid browser import leaves the existing week intact', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.local.set('flexweek.week.v1', '{broken');
  const count = h.requests.length;
  await h.elements.get('import-week').listeners.click();
  assert.equal(h.run('weekState().blocks[0].title'), 'Math');
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
    return response(200, { week_start: MONDAY, blocks: [task], revision: 1 });
  });
  await h.elements.get('import-week').listeners.click();
  assert.equal(h.local.has('flexweek.week.v1'), false);
  assert.equal(h.run('weekState().dirty'), false);
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

test('a bare ISO date is a calendar date, not a UTC instant', async () => {
  const h = harness();
  await tick();
  // Read as UTC in this zone, "2026-09-07" would be the Sunday before it.
  assert.equal(h.run('new Date("2026-09-07").getDay()'), 0);
  assert.equal(h.run('isWeekStart("2026-09-07")'), true);
  assert.equal(h.run('mondayOf("2026-09-07")'), '2026-09-07');
  assert.equal(h.run('dateForDay("2026-09-07", 0)'), '2026-09-07');
  assert.equal(h.run('currentWeekStart()'), '2026-09-07');
  assert.equal(h.run('shortDate("2026-09-07")'), 'Sep 7');
});

test('week arithmetic stays on Mondays across month, year and clock changes', async () => {
  const h = harness();
  await tick();
  assert.equal(h.run('mondayOf("2026-09-13")'), '2026-09-07');
  assert.equal(h.run('mondayOf("2027-01-01")'), '2026-12-28');
  assert.equal(h.run('shiftWeek("2026-09-07", -1)'), '2026-08-31');
  assert.equal(h.run('shiftWeek("2026-08-31", 1)'), '2026-09-07');
  assert.equal(h.run('shiftWeek("2026-12-28", 1)'), '2027-01-04');
  assert.equal(h.run('shiftWeek("2027-01-04", -1)'), '2026-12-28');
  // Daylight saving starts on 2026-03-08 in this zone.
  assert.equal(h.run('shiftWeek("2026-03-02", 1)'), '2026-03-09');
  assert.equal(h.run('dateForDay("2026-12-28", 6)'), '2027-01-03');
  assert.equal(h.run('isWeekStart("2026-09-08")'), false);
  assert.equal(h.run('isWeekStart("1999-12-27")'), false);
  assert.equal(h.run('isWeekStart("2026-02-30")'), false);
  assert.equal(h.run('isWeekStart("07/09/2026")'), false);
});

test('day headers show the dates of the week on screen', async () => {
  const h = harness();
  await h.login();
  assert.deepEqual(h.dayHeads(),
    ['Mon Sep 7', 'Tue Sep 8', 'Wed Sep 9', 'Thu Sep 10', 'Fri Sep 11', 'Sat Sep 12', 'Sun Sep 13']);
  h.handle(async path => response(200, { week_start: weekOf(path), blocks: [], revision: 0 }));
  await h.elements.get('week-prev').listeners.click();
  assert.deepEqual(h.dayHeads(),
    ['Mon Aug 31', 'Tue Sep 1', 'Wed Sep 2', 'Thu Sep 3', 'Fri Sep 4', 'Sat Sep 5', 'Sun Sep 6']);
});

test('previous, next and Today open the expected Monday and render what came back', async () => {
  const h = harness();
  await h.login(1, [task]);
  const asked = [];
  h.handle(async path => {
    asked.push(path);
    return response(200, { week_start: weekOf(path), blocks: [{ ...task, id: 'lab', title: 'Science' }], revision: 4 });
  });
  await h.elements.get('week-prev').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-08-31');
  assert.equal(h.run('weekState().revision'), 4);
  assert.equal(h.run('weekState().blocks[0].title'), 'Science');
  assert.equal(h.elements.get('week-label').textContent, 'Week of Aug 31, 2026');
  await h.elements.get('week-next').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-09-07');
  await h.elements.get('week-next').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-09-14');
  await h.elements.get('week-today').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-09-07');
  assert.deepEqual(asked, [
    '/api/week?week_start=2026-08-31',
    '/api/week?week_start=2026-09-07',
    '/api/week?week_start=2026-09-14',
    '/api/week?week_start=2026-09-07',
  ]);
  // The year boundary: December 2026 into January 2027.
  h.elements.get('week-jump').value = '2026-12-28';
  await h.elements.get('week-jump').listeners.change();
  assert.equal(h.run('selectedWeek'), '2026-12-28');
  await h.elements.get('week-next').listeners.click();
  assert.equal(h.run('selectedWeek'), '2027-01-04');
  await h.elements.get('week-prev').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-12-28');
});

test('an account whose data sits in an earlier week can still reach it', async () => {
  const h = harness();
  await h.login(1, [], ['2026-08-24']);
  assert.deepEqual(h.requests.slice(-3).map(r => r.path).sort(),
    ['/api/preferences', '/api/week?week_start=2026-09-07', '/api/weeks']);
  assert.deepEqual(h.elements.get('week-jump').children.map(option => option.value),
    ['2026-08-24', '2026-09-07']);
  assert.match(h.elements.get('status').textContent, /This week is empty/);
  h.handle(async path => response(200, { week_start: weekOf(path), blocks: [task], revision: 9 }));
  h.elements.get('week-jump').value = '2026-08-24';
  await h.elements.get('week-jump').listeners.change();
  assert.equal(h.run('selectedWeek'), '2026-08-24');
  assert.equal(h.run('weekState().blocks[0].title'), 'Math');
  assert.equal(h.elements.get('status').textContent, 'Saved · 0 locked, 1 flexible');
});

test('switching weeks keeps unsaved edits in the week they belong to', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.handle(async () => { throw new Error('Offline'); });
  assert.equal(await h.run('saveWeek()'), false);
  h.handle(async path => response(200, { week_start: weekOf(path), blocks: [], revision: 6 }));
  await h.elements.get('week-next').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-09-14');
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(h.run('weekState().dirty'), false);
  assert.equal(h.run('weekState("2026-09-07").blocks[0].title'), 'Math');
  assert.equal(h.run('weekState("2026-09-07").dirty'), true);
  assert.match(h.elements.get('status').textContent, /Unsaved edits kept in Sep 7/);
  assert.deepEqual(h.elements.get('week-jump').children.map(option => option.value),
    ['2026-09-07', '2026-09-14']);
  const before = h.requests.length;
  await h.elements.get('week-prev').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-09-07');
  assert.equal(h.run('weekState().blocks[0].title'), 'Math');
  assert.equal(h.run('weekState().dirty'), true);
  assert.equal(h.requests.length, before, 'a week holding unsaved edits must not be refetched');
  assert.equal(h.elements.get('save-actions').hidden, false);
});

test('a save sends the week_start of the week on screen, not a stale one', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.handle(async path => response(200, { week_start: weekOf(path), blocks: [], revision: 5 }));
  await h.elements.get('week-next').listeners.click();
  let body = null;
  h.handle(async (_path, options) => {
    body = JSON.parse(options.body);
    return response(200, { week_start: '2026-09-14', blocks: [], revision: 6 });
  });
  h.run('weekState().blocks.push({id:"essay",kind:"flexible",title:"Essay",duration_min:30,days:[1]})');
  assert.equal(await h.run('saveWeek()'), true);
  assert.equal(body.week_start, '2026-09-14');
  assert.equal(body.revision, 5);
  assert.deepEqual(body.blocks.map(block => block.title), ['Essay']);
  assert.equal(h.run('weekState("2026-09-14").revision'), 6);
  assert.equal(h.run('weekState("2026-09-07").revision'), 0);
  assert.deepEqual(h.run('weekState("2026-09-07").blocks.map(b => b.title)'), ['Math']);
  // Only the week that was actually saved joins the list of saved weeks.
  assert.deepEqual(h.elements.get('week-jump').children.map(option => option.value), ['2026-09-14']);
});
