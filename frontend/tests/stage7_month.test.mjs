process.env.TZ = 'America/Los_Angeles';

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';
import { runAppScripts } from './app-scripts.mjs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const response = (status, data) => ({ status, ok: status < 400, json: async () => structuredClone(data) });
const tick = () => new Promise(resolve => setImmediate(resolve));
const NOW = new Date(2026, 8, 10, 12, 0, 0);

class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [NOW.getTime()])); }
  static now() { return NOW.getTime(); }
}

function harness() {
  const elements = new Map();
  const all = [];
  const requests = [];
  function matches(item, selector) {
    if (selector.startsWith('.')) return item.classList.contains(selector.slice(1));
    return false;
  }
  function connected() {
    const found = [];
    const seen = new Set();
    function visit(item) {
      if (!item || seen.has(item)) return;
      seen.add(item); found.push(item); item.children.forEach(visit);
    }
    elements.forEach(visit);
    return found;
  }
  function element() {
    const classes = new Set();
    const style = { setProperty(name, value) { this[name] = value; }, removeProperty(name) { delete this[name]; } };
    const item = {
      value: '', textContent: '', hidden: false, disabled: false, checked: false, open: false,
      dataset: {}, style, children: [], listeners: {},
      get className() { return [...classes].join(' '); },
      set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach(v => classes.add(v)); },
      classList: { add: v => classes.add(v), remove: v => classes.delete(v), contains: v => classes.has(v) },
      set innerHTML(_value) { this.children = []; }, get innerHTML() { return ''; },
      addEventListener(name, fn) { this.listeners[name] = fn; }, removeEventListener(name) { delete this.listeners[name]; },
      appendChild(child) { this.children.push(child); child.parentNode = this; },
      replaceChildren(...children) { this.children = children; children.forEach(child => { child.parentNode = this; }); },
      querySelectorAll(selector) { return this.children.filter(child => matches(child, selector)); },
      querySelector(selector) { return this.children.find(child => matches(child, selector)) || null; },
      closest() { return null; }, contains(node) { return this === node || this.children.includes(node); },
      getBoundingClientRect() { return { top: 0, bottom: 100, left: 0, right: 320, width: 320, height: 100 }; },
      setPointerCapture() {}, reset() {}, focus() {}, click() {}, scrollIntoView() {},
      showModal() { this.open = true; }, close() { this.open = false; },
      setAttribute(name, value) { this[name] = String(value); }, removeAttribute(name) { delete this[name]; },
    };
    all.push(item);
    return item;
  }
  for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], element());
  function FakeNotification() {}
  FakeNotification.permission = 'default';
  FakeNotification.requestPermission = async () => 'denied';
  let handler = async () => response(401, { detail: 'Please sign in' });
  const context = vm.createContext({
    document: {
      getElementById: id => elements.get(id), documentElement: { dataset: { theme: 'nocturne' } },
      createElement: element, addEventListener() {}, hidden: false,
      querySelectorAll: selector => connected().filter(item => selector.split(',').some(part => matches(item, part.trim()))),
    },
    window: { addEventListener() {}, AudioContext: class {}, open: () => ({}) },
    localStorage: { getItem() { return null; }, removeItem() {} },
    sessionStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
    fetch: async (path, request) => { requests.push({ path, request }); return handler(path, request); },
    getComputedStyle: () => ({ getPropertyValue: () => '2.75rem' }),
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    setTimeout, clearTimeout, setInterval, clearInterval, AbortController, structuredClone, console,
    confirm: () => true, Date: FixedDate, Notification: FakeNotification,
    crypto: globalThis.crypto, TextEncoder, Blob,
    URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} },
  });
  runAppScripts(vm, context);
  return {
    elements, requests, all,
    run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    connected,
    find: (className, predicate = () => true) => connected().filter(item => item.classList.contains(className)).find(predicate),
    async login(id = 1) {
      await tick();
      handler = async path => {
        if (path.startsWith('/api/assignments')) return response(200, { assignments: [] });
        if (path === '/api/weeks') return response(200, { weeks: [] });
        if (path.startsWith('/api/week')) return response(200, { week_start: '2026-09-07', blocks: [], revision: 0 });
        if (path === '/api/preferences') return response(200, { theme: 'nocturne' });
        return response(404, { detail: 'Unexpected request ' + path });
      };
      await vm.runInContext(`loadAccount({id:${id},username:'student${id}'})`, context);
    },
  };
}

function snapshot(month = '2026-09') {
  return {
    month, start: month + '-01', end: month + '-30', grid_start: '2026-08-31', grid_end: '2026-10-04',
    days: [
      { date: '2026-08-31', week_start: '2026-08-31', in_month: false, due_ids: [], session_count: 0, locked_count: 0, scheduled_min: 0, focus_min: 0 },
      { date: '2026-09-15', week_start: '2026-09-14', in_month: true, due_ids: [], session_count: 1, locked_count: 1, scheduled_min: 450, focus_min: 0 },
      { date: '2026-09-16', week_start: '2026-09-14', in_month: true, due_ids: ['essay', 'quiz'], session_count: 1, locked_count: 0, scheduled_min: 60, focus_min: 0 },
    ],
    deadlines: [
      { id: 'essay', title: 'History essay', due: '2026-09-16T23:59', date: '2026-09-16', completed: false, estimate_min: 120, unplanned_min: 60, revision: 1 },
      { id: 'quiz', title: 'Biology quiz', due: '2026-09-16T20:00', date: '2026-09-16', completed: true, estimate_min: 30, unplanned_min: 0, revision: 2 },
    ],
    projects: [{ id: 'essay', title: 'History essay', due: '2026-09-16T23:59', date: '2026-09-16', completed: false,
      estimate_min: 120, unplanned_min: 60, revision: 1, session_dates: ['2026-09-15', '2026-09-16'],
      has_notes: true, has_links: true, checklist_total: 4, checklist_done: 2 }],
    overdue: [{ id: 'late', title: 'Late lab', due: '2026-08-15T17:00', date: '2026-08-15', completed: false,
      estimate_min: 45, unplanned_min: 45, revision: 1 }],
    unscheduled: { session_count: 0, minutes: 0 },
  };
}

async function showMonth(h, data = snapshot()) {
  h.handle(async path => path.startsWith('/api/month') ? response(200, data) : response(404, { detail: 'Unexpected request ' + path }));
  return h.run(`plannerView='month';selectedMonth='${data.month}';renderWeekNav();renderWeek();refreshMonthData()`);
}

test('Month renders due and completed work, compact time, projects and overdue without exposing details', async () => {
  const h = harness();
  await h.login();
  await showMonth(h);
  const day = h.find('month-day', item => item.dataset.date === '2026-09-16');
  assert.ok(day.children.some(item => item.textContent === 'History essay'));
  assert.ok(day.children.some(item => item.textContent === 'Biology quiz · Done' && item.classList.contains('is-completed')));
  assert.match(day.ariaLabel, /History essay due/);
  assert.match(day.ariaLabel, /Biology quiz completed/);
  assert.equal(h.find('month-day', item => item.dataset.date === '2026-09-15').children.at(-1).textContent, '1 study · 1 fixed · 7 h 30 min');
  assert.equal(h.elements.get('month-overdue-section').hidden, false);
  assert.equal(h.elements.get('month-projects-section').hidden, false);
  assert.match(h.elements.get('month-projects').children[0].textContent + h.elements.get('month-projects').children[0].children.map(c => c.textContent).join(' '), /Checklist 2\/4 · Notes · Links/);
  assert.doesNotMatch(h.connected().map(item => item.textContent).join(' '), /secret note|https:\/\//);
});

test('an empty month clears old rows and reports the empty saved calendar', async () => {
  const h = harness();
  await h.login();
  await showMonth(h);
  const empty = snapshot();
  empty.deadlines = []; empty.projects = []; empty.overdue = [];
  empty.days = empty.days.map(day => ({ ...day, due_ids: [], session_count: 0, locked_count: 0, scheduled_min: 0 }));
  h.handle(async () => response(200, empty));
  await h.run('refreshMonthData()');
  assert.equal(h.elements.get('month-state').textContent, 'Nothing is due or scheduled this month.');
  assert.equal(h.elements.get('month-overdue').children.length, 0);
  assert.equal(h.elements.get('month-projects').children.length, 0);
});

test('one deadline on an otherwise blank month says it is early, not broken', async () => {
  const h = harness();
  await h.login();
  const sparse = snapshot();
  sparse.projects = []; sparse.overdue = [];
  sparse.deadlines = [sparse.deadlines[0]];
  sparse.days = sparse.days.map(day => ({ ...day, session_count: 0, locked_count: 0, scheduled_min: 0,
    due_ids: day.date === '2026-09-16' ? ['essay'] : [] }));
  await showMonth(h, sparse);
  assert.equal(h.elements.get('month-state').textContent,
    'Only one thing is due so far. The rest of the month fills in as you plan your work.');
});

test('several deadlines with nothing planned are counted in the same line', async () => {
  const h = harness();
  await h.login();
  const sparse = snapshot();
  sparse.projects = []; sparse.overdue = [];
  sparse.days = sparse.days.map(day => ({ ...day, session_count: 0, locked_count: 0, scheduled_min: 0 }));
  await showMonth(h, sparse);
  assert.equal(h.elements.get('month-state').textContent,
    'Only 2 things are due so far. The rest of the month fills in as you plan your work.');
});

test('a month with work planned on it is not called early', async () => {
  const h = harness();
  await h.login();
  await showMonth(h);
  // The stub keeps stale text after replaceChildren, so check the sentence was never written.
  assert.doesNotMatch(h.elements.get('month-state').textContent, /due so far/);
});

test('a late response for the previous month cannot replace the selected month', async () => {
  const h = harness();
  await h.login();
  let finishSeptember;
  h.handle(async path => path.endsWith('2026-09') ? new Promise(resolve => { finishSeptember = resolve; }) : response(200, { ...snapshot('2026-10'), deadlines: [] }));
  const september = h.run("plannerView='month';selectedMonth='2026-09';refreshMonthData()");
  await tick();
  h.run('shiftSelectedMonth(1)');
  await tick();
  finishSeptember(response(200, snapshot()));
  await september;
  await tick();
  assert.equal(h.run('selectedMonth'), '2026-10');
  assert.equal(h.run('monthSnapshot.month'), '2026-10');
  assert.equal(h.elements.get('week-label').textContent, 'October 2026');
});

test('a late older request for the same month cannot replace the newest response', async () => {
  const h = harness();
  await h.login();
  let finishFirst;
  let finishSecond;
  let calls = 0;
  h.handle(async () => new Promise(resolve => {
    calls += 1;
    if (calls === 1) finishFirst = resolve;
    else finishSecond = resolve;
  }));
  const first = h.run("plannerView='month';selectedMonth='2026-09';refreshMonthData()");
  await tick();
  const second = h.run('refreshMonthData()');
  await tick();
  finishSecond(response(200, { ...snapshot(), deadlines: [] }));
  await second;
  finishFirst(response(200, snapshot()));
  await first;
  assert.equal(h.run('monthSnapshot.deadlines.length'), 0);
});

test('a late response from another account cannot populate the current account month', async () => {
  const h = harness();
  await h.login(1);
  let finishFirst;
  h.handle(async () => new Promise(resolve => { finishFirst = resolve; }));
  const first = h.run("plannerView='month';selectedMonth='2026-09';refreshMonthData()");
  await tick();
  h.run("epoch+=1;clearMonthState();account={id:2,username:'student2'};plannerView='month';selectedMonth='2026-09'");
  h.handle(async () => response(200, { ...snapshot(), deadlines: [] }));
  await h.run('refreshMonthData()');
  finishFirst(response(200, snapshot()));
  await first;
  assert.equal(h.run('account.id'), 2);
  assert.equal(h.run('monthSnapshot.deadlines.length'), 0);
});

test('signing out removes month deadlines and project text from the DOM', async () => {
  const h = harness();
  await h.login();
  await showMonth(h);
  assert.ok(h.elements.get('month-projects').children.length);
  h.run("signedOut('Done', false)");
  assert.equal(h.run('monthSnapshot'), null);
  assert.equal(h.elements.get('month-calendar').children.length, 0);
  assert.equal(h.elements.get('month-overdue').children.length, 0);
  assert.equal(h.elements.get('month-projects').children.length, 0);
});

test('loading clears old content and an error offers a working Retry', async () => {
  const h = harness();
  await h.login();
  await showMonth(h);
  let finish;
  h.handle(async () => new Promise(resolve => { finish = resolve; }));
  const loading = h.run('refreshMonthData()');
  await tick();
  assert.match(h.elements.get('month-state').textContent, /^Loading September 2026/);
  assert.equal(h.elements.get('month-calendar').children.length, 0);
  finish(response(500, { detail: 'Calendar unavailable' }));
  await loading;
  assert.match(h.elements.get('month-state').children[0].textContent, /Calendar unavailable/);
  const retry = h.elements.get('month-state').children[1];
  h.handle(async () => response(200, snapshot()));
  retry.listeners.click();
  await tick(); await tick();
  assert.equal(h.run('monthSnapshot.month'), '2026-09');
});

test('month navigation crosses years, Today returns to this month, and bounds disable arrows', async () => {
  const h = harness();
  await h.login();
  h.handle(async path => response(200, { ...snapshot(new URL(path, 'http://test').searchParams.get('month')), deadlines: [] }));
  h.run("plannerView='month';selectedMonth='2026-12';renderWeekNav();renderWeek()");
  h.run('shiftSelectedMonth(1)');
  assert.equal(h.run('selectedMonth'), '2027-01');
  h.run('openCurrentMonth()');
  assert.equal(h.run('selectedMonth'), '2026-09');
  h.run("selectedMonth='2000-01';renderMonthView()");
  assert.equal(h.elements.get('week-prev').disabled, true);
  assert.equal(h.run('shiftSelectedMonth(-1)'), false);
  h.run("selectedMonth='2099-12';renderMonthView()");
  assert.equal(h.elements.get('week-next').disabled, true);
  assert.equal(h.run('shiftSelectedMonth(1)'), false);
});

test('entering Month anchors Day to its month and Week to Thursday while preferred view stays unchanged', async () => {
  const h = harness();
  await h.login();
  h.handle(async () => response(200, snapshot()));
  h.run("prefs.preferred_view='week';plannerView='day';selectedDay='2026-10-01';setPlannerView('month')");
  assert.equal(h.run('selectedMonth'), '2026-10');
  assert.equal(h.run('prefs.preferred_view'), 'week');
  h.run("plannerView='week';selectedWeek='2026-09-28';setPlannerView('month')");
  assert.equal(h.run('selectedMonth'), '2026-10');
});

test('opening a month date switches to Day only after authoritative week data succeeds', async () => {
  const h = harness();
  await h.login();
  await showMonth(h);
  h.handle(async path => {
    if (path.startsWith('/api/week')) return response(200, { week_start: '2026-09-14', blocks: [], revision: 0 });
    if (path.startsWith('/api/assignments')) return response(200, { assignments: [] });
    if (path.startsWith('/api/day')) return response(200, { date: '2026-09-16', due_soon: [], workload: null });
    return response(404, { detail: 'Unexpected request ' + path });
  });
  assert.equal(await h.run("openMonthDay('2026-09-16')"), true);
  assert.equal(h.run('plannerView'), 'day');
  assert.equal(h.run('selectedDay'), '2026-09-16');
  assert.equal(h.run('selectedWeek'), '2026-09-14');
});

test('a failed date load leaves Month and its snapshot intact', async () => {
  const h = harness();
  await h.login();
  await showMonth(h);
  h.handle(async path => path.startsWith('/api/week') ? response(500, { detail: 'Offline' }) : response(200, { assignments: [] }));
  assert.equal(await h.run("openMonthDay('2026-09-16')"), false);
  assert.equal(h.run('plannerView'), 'month');
  assert.equal(h.run('monthSnapshot.month'), '2026-09');
  assert.match(h.elements.get('status').textContent, /Could not open that week/);
});

test('a restore returns to the same Month and refreshes its saved snapshot', async () => {
  const h = harness();
  await h.login();
  h.handle(async path => path.startsWith('/api/month')
    ? response(200, snapshot())
    : response(404, { detail: 'Unexpected request ' + path }));
  await h.run("keepPlannerPlace({week:selectedWeek,day:selectedDay,month:'2026-09',view:'month'})");
  assert.equal(h.run('plannerView'), 'month');
  assert.equal(h.run('selectedMonth'), '2026-09');
  assert.equal(h.run('monthSnapshot.month'), '2026-09');
});

test('Month hides editing controls, warns about dirty saved-only data, and ships no Year control', async () => {
  const h = harness();
  await h.login();
  h.run('weekState().dirty=true');
  await showMonth(h);
  assert.equal(h.elements.get('planner').dataset.view, 'month');
  assert.equal(h.elements.get('week-jump-label').hidden, true);
  assert.equal(h.elements.get('sidebar-toggle').hidden, true);
  assert.equal(h.elements.get('add-homework').hidden, true);
  assert.equal(h.elements.get('unfinished-review').hidden, true);
  assert.equal(h.elements.get('solve').hidden, true);
  assert.equal(h.elements.get('month-saved-warning').hidden, false);
  assert.equal(h.elements.has('view-year'), false);
});

test('the saved-only warning carries its own words and is written only when it changes', async () => {
  const h = harness();
  await h.login();
  const warning = h.elements.get('month-saved-warning');
  // A live region is announced when its text changes, so count the writes.
  let text = '';
  const writes = [];
  Object.defineProperty(warning, 'textContent', {
    get: () => text,
    set: value => { text = value; writes.push(value); },
  });

  assert.match(html.match(/<[^>]*\bid="month-saved-warning"[^>]*>/)[0], /aria-live="polite"/,
    'a warning that only appears is silent without a live region');

  h.run('weekState().dirty=true');
  await showMonth(h);
  assert.equal(warning.hidden, false);
  assert.equal(warning.textContent,
    'This month shows saved changes only. Save your week to include recent edits.');

  const announcements = writes.filter(value => value).length;
  await h.run('renderMonthView()');
  assert.equal(writes.filter(value => value).length, announcements,
    'redrawing the same warning must not announce it again');

  h.run('weekState().dirty=false');
  await h.run('renderMonthView()');
  assert.equal(warning.hidden, true);
  assert.equal(warning.textContent, '');
});

test('the lower boundary week can open January 1 2000 but no other 1999 Monday is valid', async () => {
  const h = harness();
  await h.login();
  h.run("plannerView='month';selectedMonth='2000-01'");
  h.handle(async path => {
    if (path.startsWith('/api/week')) return response(200, { week_start: '1999-12-27', blocks: [], revision: 0 });
    if (path.startsWith('/api/assignments')) return response(200, { assignments: [] });
    if (path.startsWith('/api/day')) return response(200, { date: '2000-01-01', due_soon: [], workload: null });
    return response(404, { detail: 'Unexpected request ' + path });
  });
  assert.equal(await h.run("openMonthDay('2000-01-01')"), true);
  assert.equal(h.run('selectedWeek'), '1999-12-27');
  assert.equal(h.run("isWeekStart('1999-12-20')"), false);
});


test('a day says how much of its work is already behind you', async () => {
  const h = harness();
  await h.login();
  const data = snapshot();
  data.days = [
    { date: '2026-09-15', week_start: '2026-09-14', in_month: true, due_ids: [], session_count: 2, locked_count: 0, scheduled_min: 120, focus_min: 120 },
    { date: '2026-09-16', week_start: '2026-09-14', in_month: true, due_ids: [], session_count: 2, locked_count: 0, scheduled_min: 120, focus_min: 60 },
  ];
  await showMonth(h, data);

  assert.equal(h.find('month-day', item => item.dataset.date === '2026-09-15').children.at(-1).textContent,
    '2 study · 2 h · all done');
  assert.equal(h.find('month-day', item => item.dataset.date === '2026-09-16').children.at(-1).textContent,
    '2 study · 2 h · 1 h done');
});

test('work that has no day yet is reported rather than silently dropped', async () => {
  const h = harness();
  await h.login();
  const many = snapshot();
  many.unscheduled = { session_count: 3, minutes: 150 };
  await showMonth(h, many);
  assert.equal(h.elements.get('month-unscheduled').hidden, false);
  assert.equal(h.elements.get('month-unscheduled').textContent,
    '3 study sessions (2 h 30 min) are planned this month but have no day yet.');

  const one = snapshot();
  one.unscheduled = { session_count: 1, minutes: 45 };
  h.handle(async () => response(200, one));
  await h.run('refreshMonthData()');
  assert.equal(h.elements.get('month-unscheduled').textContent,
    '1 study session (45 min) is planned this month but has no day yet.');

  h.handle(async () => response(200, snapshot()));
  await h.run('refreshMonthData()');
  assert.equal(h.elements.get('month-unscheduled').hidden, true);
});

test('a month holding only undated work does not claim nothing is scheduled', async () => {
  const h = harness();
  await h.login();
  const data = snapshot();
  data.deadlines = []; data.projects = []; data.overdue = [];
  data.days = data.days.map(day => ({ ...day, due_ids: [], session_count: 0, locked_count: 0, scheduled_min: 0, focus_min: 0 }));
  data.unscheduled = { session_count: 2, minutes: 90 };
  await showMonth(h, data);

  assert.notEqual(h.elements.get('month-state').textContent, 'Nothing is due or scheduled this month.');
  assert.equal(h.elements.get('month-unscheduled').hidden, false);
});

test('a month payload without the unscheduled total is refused, not half-drawn', async () => {
  const h = harness();
  await h.login();
  const broken = snapshot();
  delete broken.unscheduled;
  await showMonth(h, broken);
  await tick();
  assert.equal(h.run('monthSnapshot'), null);
  assert.match(h.elements.get('month-state').children[0].textContent, /invalid month/);
});
