// A week_start is a calendar label, so the date helpers must not read one as a
// UTC instant. Only a zone west of Greenwich exposes that mistake, so pin one.
process.env.TZ = 'America/Los_Angeles';

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';
import { runAppScripts } from './app-scripts.mjs';

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

function harness(options = {}) {
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
      // The app only ever assigns "", which clears a real element's children.
      set innerHTML(value) { this.children = []; },
      get innerHTML() { return ''; },
      addEventListener(name, handler) { this.listeners[name] = handler; },
      appendChild(child) { this.children.push(child); },
      replaceChildren() { this.children = []; },
      querySelectorAll() { return []; }, reset() {}, focus() {}, click() {}, scrollIntoView() {},
    };
    allElements.push(el);
    return el;
  }
  for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], element());
  const local = new Map();
  let handler = options.handler || (async () => response(401, { detail: 'Please sign in' }));
  const requests = [];
  const context = vm.createContext({
    document: {
      getElementById: id => { assert.ok(elements.has(id), `Missing HTML element ${id}`); return elements.get(id); },
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
    confirm: () => true, Date: FixedDate, matchMedia: options.matchMedia,
    location: options.location, history: options.history,
  });
  runAppScripts(vm, context);
  return {
    elements, local, requests, allElements,
    run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    dayHeads: () => elements.get('week').children
      .filter(child => child.className === 'day-head')
      .map(head => head.children.map(part => part.textContent).join(' ')),
    async login(id = 1, blocks = [], saved = [], owned = []) {
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

test('solve renders student-facing explanations, slack, and click-to-highlight', async () => {
  const h = harness();
  await h.login(1, [task]);
  h.handle(async path => {
    assert.equal(path, '/api/solve');
    return response(200, {
      placed: [{ ...task, days: [0], start: '06:00' }], unplaced: [], moves: [],
      explanations: [{
        block_id: 'homework', message: 'Limited room: scheduled to finish 2h before the deadline.',
        reason: null, slack_min: 120, slack_status: 'tight',
      }], failed_constraints: [], solve_ms: 1, complete: true,
    });
  });

  await h.run('solveWeek()');

  const block = h.allElements.findLast(el => el.classList.contains('block') && el.dataset.id === 'homework');
  assert.ok(block);
  assert.ok(block.children.some(child => child.textContent === 'Tight fit'));
  const detail = h.elements.get('debug-unplaced').children[0].children[0];
  detail.listeners.click();
  assert.equal(block.classList.contains('is-highlighted'), true);
  assert.match(detail.textContent, /Limited room/);
});

test('miss recovery sends the prior placement, saves one missed day, and lists a day-changing move', async () => {
  const h = harness();
  const school = {
    id: 'school', kind: 'locked', title: 'School', duration_min: 1020,
    days: [0], start: '06:00', priority: 1, energy: 'medium',
  };
  const homework = { ...task, days: [0, 1], energy: 'high', priority: 3 };
  await h.login(1, [school, homework]);
  const previous = [school, { ...homework, days: [1], start: '06:00' }];
  h.run(`weekState().trace = ${JSON.stringify({ placed: previous })}`);
  let resolveSave;
  h.handle(async (path, options) => {
    const payload = JSON.parse(options.body);
    if (path === '/api/solve') {
      assert.deepEqual(payload.recover.previous_placed, previous);
      assert.equal(payload.recover.missed_block_id, 'school');
      assert.equal(payload.recover.missed_day, 0);
      return response(200, {
        placed: [{ ...homework, days: [0], start: '06:00' }], unplaced: [],
        moves: [{ block_id: 'homework', reason: 'RESHUFFLE_AFTER_MISS', from_day: 1,
          from_start: '06:00', to_day: 0, to_start: '06:00' }],
        explanations: [{ block_id: 'homework', reason: 'RESHUFFLE_AFTER_MISS',
          message: 'Moved after a missed block so the rest of the week still fits.' }],
        failed_constraints: [], solve_ms: 1, complete: true,
      });
    }
    assert.equal(path, '/api/week');
    assert.deepEqual(payload.blocks[0].missed_days, [0]);
    return new Promise(done => {
      resolveSave = () => done(response(200, { week_start: MONDAY, blocks: payload.blocks, revision: 1 }));
    });
  });

  const recovering = h.run("recoverMissedOccurrence('school', 0)");
  await tick();
  await tick();

  assert.equal(h.run('JSON.stringify(weekState().blocks[0].missed_days)'), '[0]');
  assert.equal(h.run('weekState().dirty'), true);
  assert.doesNotMatch(h.elements.get('status').textContent, /^Saved/);
  assert.equal(h.elements.get('debug-changes').hidden, false);
  assert.ok(h.allElements.findLast(el =>
    el.classList.contains('missed-block') && el.dataset.id === 'school'));
  const changes = h.elements.get('debug-moves').children.map(li => li.children[0].textContent);
  assert.ok(changes.some(text => text.includes('Tue 06:00 → Mon 06:00')));
  resolveSave();
  await recovering;
  assert.equal(h.run('weekState().dirty'), false);
});

test('boot requires sign-in and never fetches a demo or exposes legacy data', async () => {
  const h = harness();
  h.local.set('flexweek.week.v1', JSON.stringify({ blocks: [task] }));
  await tick();
  assert.equal(h.elements.get('planner').hidden, true);
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.deepEqual(h.requests.map(r => r.path), ['/api/auth/me']);
});

function signedInServer(extra = async () => undefined) {
  return async (path, options) => {
    const answer = await extra(path, options);
    if (answer) return answer;
    if (path === '/api/auth/me') return response(200, { id: 4, username: 'crash_student' });
    if (path.startsWith('/api/weeks')) return response(200, { weeks: [MONDAY] });
    if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks: [task], revision: 1 });
    return response(200, { theme: 'slate' });
  };
}

async function settled(done) {
  for (let i = 0; i < 30 && !done(); i++) await tick();
}

test('a page the desktop app reopened after it stopped turns solid and is solved again', async () => {
  const replaced = [];
  const h = harness({
    location: { search: '?recovered=1', pathname: '/' },
    history: { replaceState: (_state, _title, url) => replaced.push(url) },
    handler: signedInServer(async path => path === '/api/solve' ? response(200, {
      placed: [{ ...task, start: '15:00' }], unplaced: [], moves: [], explanations: [],
      failed_constraints: [], solve_ms: 1, complete: true,
    }) : undefined),
  });
  await settled(() => h.elements.get('status').textContent.startsWith('FlexWeek reopened'));

  assert.equal(h.run('document.documentElement.dataset.frost'), 'off');
  assert.deepEqual(replaced, ['/'], 'the recovery marker was not removed from the address');
  assert.equal(h.requests.filter(r => r.path === '/api/solve').length, 1);
  assert.equal(h.elements.get('planner').hidden, false);
  assert.equal(h.elements.get('status').textContent,
    'FlexWeek reopened after a display problem. Saved week · 1 task placed');
});

test('an ordinary page load keeps the frosted look and does not solve by itself', async () => {
  const h = harness({ location: { search: '', pathname: '/' }, handler: signedInServer() });
  await settled(() => h.elements.get('account-name').textContent === 'crash_student');

  assert.equal(h.elements.get('planner').hidden, false);
  assert.equal(h.run('document.documentElement.dataset.frost'), undefined);
  assert.equal(h.requests.some(r => r.path === '/api/solve'), false);
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
  h.elements.get('debug').hidden = false;
  h.elements.get('flex-note').textContent = 'Unplaced after Solve — reasons below.';
  await h.elements.get('week-prev').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-08-31');
  assert.equal(h.run('weekState().revision'), 4);
  // A solve describes the week it ran on, so it must not follow the reader.
  assert.equal(h.elements.get('debug').hidden, true);
  assert.equal(h.elements.get('flex-note').textContent, 'Press Solve to place these around school and sports.');
  assert.equal(h.run('weekState().blocks[0].title'), 'Science');
  assert.equal(h.elements.get('week-label').textContent, 'Week of Aug 31, 2026');
  await h.elements.get('week-next').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-09-07');
  await h.elements.get('week-next').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-09-14');
  await h.elements.get('week-today').listeners.click();
  assert.equal(h.run('selectedWeek'), '2026-09-07');
  // Opening a week also refreshes the assignments it plans against.
  assert.deepEqual(asked, ['2026-08-31', '2026-09-07', '2026-09-14', '2026-09-07'].flatMap(week => [
    `/api/week?week_start=${week}`,
    `/api/assignments?week_start=${week}&include_completed=true`,
  ]));
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
  assert.deepEqual(h.requests.slice(-4).map(r => r.path).sort(),
    ['/api/assignments?week_start=2026-09-07&include_completed=true', '/api/preferences',
      '/api/week?week_start=2026-09-07', '/api/weeks']);
  assert.deepEqual(h.elements.get('week-jump').children.map(option => option.value),
    ['2026-08-24', '2026-09-07']);
  assert.match(h.elements.get('status').textContent, /This week is empty/);
  h.handle(async path => response(200, { week_start: weekOf(path), blocks: [task], revision: 9 }));
  h.elements.get('week-jump').value = '2026-08-24';
  await h.elements.get('week-jump').listeners.change();
  assert.equal(h.run('selectedWeek'), '2026-08-24');
  assert.equal(h.run('weekState().blocks[0].title'), 'Math');
  assert.equal(h.elements.get('status').textContent, 'Saved · 0 fixed, 1 flexible');
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

test('a visitor with no session first sees Create account, and Log in is a separate screen', async () => {
  const h = harness();
  await tick();
  assert.equal(h.elements.get('register-screen').hidden, false);
  assert.equal(h.elements.get('login-screen').hidden, true);
  assert.equal(h.elements.get('reconnect').hidden, true);
  assert.equal(h.elements.get('planner').hidden, true);

  h.elements.get('register-username').value = 'returning_student';
  h.elements.get('show-login').listeners.click();
  assert.equal(h.elements.get('register-screen').hidden, true);
  assert.equal(h.elements.get('login-screen').hidden, false);
  assert.equal(h.elements.get('login-username').value, 'returning_student');

  const posts = [];
  h.handle(async (path, options) => {
    if (path.startsWith('/api/auth/')) {
      posts.push({ path, body: JSON.parse(options.body) });
      return response(200, { id: 7, username: 'returning_student' });
    }
    if (path.startsWith('/api/weeks')) return response(200, { weeks: [] });
    if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks: [task], revision: 1 });
    return response(200, { theme: 'nocturne' });
  });
  h.elements.get('login-password').value = 'correct horse battery';
  await h.elements.get('login-form').listeners.submit({ preventDefault() {} });
  assert.deepEqual(posts, [{
    path: '/api/auth/login', body: { username: 'returning_student', password: 'correct horse battery' },
  }]);
  assert.equal(h.elements.get('login-password').value, '');
  assert.equal(h.elements.get('planner').hidden, false);
  assert.equal(h.elements.get('account-name').textContent, 'returning_student');
});

test('Create account posts to register, and logging out returns to the Log in screen', async () => {
  const h = harness();
  await tick();
  const posted = [];
  h.handle(async (path, options) => {
    if (path.startsWith('/api/auth/')) {
      posted.push(path);
      return path.endsWith('/logout') ? response(204) : response(200, { id: 3, username: 'new_student' });
    }
    if (path.startsWith('/api/weeks')) return response(200, { weeks: [] });
    if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks: [], revision: 0 });
    return response(200, { theme: 'nocturne' });
  });
  h.elements.get('register-username').value = 'new_student';
  h.elements.get('register-password').value = 'a long enough password';
  await h.elements.get('register-form').listeners.submit({ preventDefault() {} });
  assert.deepEqual(posted, ['/api/auth/register']);
  assert.equal(h.elements.get('planner').hidden, false);

  await h.elements.get('logout').listeners.click();
  assert.deepEqual(posted, ['/api/auth/register', '/api/auth/logout']);
  assert.equal(h.elements.get('planner').hidden, true);
  assert.equal(h.elements.get('login-screen').hidden, false);
  assert.equal(h.elements.get('register-screen').hidden, true);
});

test('a failed login shows its error on the Log in screen without leaving it', async () => {
  const h = harness();
  await tick();
  h.elements.get('show-login').listeners.click();
  h.handle(async () => response(401, { detail: 'Username or password is incorrect.' }));
  await h.elements.get('login-form').listeners.submit({ preventDefault() {} });
  assert.equal(h.elements.get('login-error').textContent, 'Username or password is incorrect.');
  assert.equal(h.elements.get('login-screen').hidden, false);
  assert.equal(h.elements.get('planner').hidden, true);
});

test('when the server cannot be reached, the first screen offers Retry connection', async () => {
  const h = harness();
  h.handle(async () => { throw new Error('Offline'); });
  h.run('reconnect()');
  await tick();
  await tick();
  assert.equal(h.elements.get('reconnect').hidden, false);
  assert.equal(h.elements.get('register-screen').hidden, false);
  assert.match(h.elements.get('status').textContent, /Could not reach FlexWeek/);
});

test('after Solve the chrome speaks plainly: results sentence, no badge for room to spare', async () => {
  const h = harness();
  const school = { id: 'school', kind: 'locked', title: 'School', duration_min: 390, days: [0], start: '08:00', priority: 1, energy: 'medium' };
  const essay = { ...task, id: 'essay', title: 'Essay', latest: 'Monday 21:00' };
  const quiz = { ...task, id: 'quiz', title: 'Quiz prep' };
  const lab = { ...task, id: 'lab', title: 'Lab report' };
  await h.login(1, [school, essay, quiz, lab]);
  h.handle(async () => response(200, {
    placed: [school, { ...essay, start: '15:00' }, { ...quiz, start: '16:00' }],
    unplaced: [lab], moves: [],
    explanations: [
      { block_id: 'essay', message: 'Room: scheduled to finish 5h before the deadline.', reason: null, slack_min: 300, slack_status: 'ok' },
      { block_id: 'quiz', message: 'Very little room: scheduled to finish 15m before the deadline.', reason: null, slack_min: 15, slack_status: 'danger' },
      { block_id: 'lab', message: 'The week is too full to place this task.', reason: 'NO_SLOT_LEFT' },
    ],
    failed_constraints: [], solve_ms: 3.25, complete: false,
  }));
  await h.run('solveWeek()');

  const badges = h.allElements.filter(el => el.classList.contains('slack-badge')).map(el => el.textContent);
  assert.deepEqual(badges, ['At risk']);
  assert.equal(h.elements.get('debug-stats').textContent,
    'Placed 2 of 3 tasks. 1 still needs a time. The reasons are below.');
  assert.equal(h.elements.get('debug-stats').title, 'Solved in 3.3 ms');

  const focusItems = h.elements.get('focus-tasks').children;
  assert.deepEqual(focusItems.map(item => item.children[0].textContent), ['Essay', 'Quiz prep']);
  assert.deepEqual(focusItems.map(item => item.children[1].textContent), ['Mon 15:00', 'Mon 16:00']);
  assert.equal(h.elements.get('focus-section').hidden, false);
});

test('the Focus section offers Quick focus before any task has a time', async () => {
  const h = harness();
  const school = { id: 'school', kind: 'locked', title: 'School', duration_min: 390, days: [0], start: '08:00', priority: 1, energy: 'medium' };
  await h.login(1, [school, task]);
  assert.equal(h.elements.get('focus-tasks').children.length, 0);
  assert.equal(h.elements.get('focus-section').hidden, false);
  h.run('signedOut()');
  assert.equal(h.elements.get('focus-section').hidden, true);
});

test('Now / Next reads as one Daily Scheduler line and is empty when the day is done', () => {
  const h = harness();
  const physics = { id: 'p', title: 'Physics', kind: 'flexible', duration_min: 60, days: [3], start: '16:00' };
  const practice = { id: 's', title: 'Practice', kind: 'locked', duration_min: 90, days: [3], start: '17:30' };
  assert.equal(h.run(`nowNextLine(${JSON.stringify({ current: physics, next: practice })}, 985)`),
    'Now: Physics · 35 min left  →  Next: Practice at 17:30');
  assert.equal(h.run(`nowNextLine(${JSON.stringify({ current: null, next: practice })}, 960)`),
    'Next: Practice at 17:30 (in 1 h 30 min)');
  assert.equal(h.run('nowNextLine({ current: null, next: null }, 1200)'), '');
});

test('a new account walks through school, sports and first homework, then Solve runs', async () => {
  const h = harness();
  await tick();
  const saves = [];
  const solves = [];
  h.handle(async (path, options) => {
    if (path === '/api/auth/register') return response(200, { id: 9, username: 'rookie' });
    if (path.startsWith('/api/weeks')) return response(200, { weeks: [] });
    if (path === '/api/changes') {
      const body = JSON.parse(options.body);
      saves.push(body);
      return response(200, {
        weeks: body.weeks.map(week => ({ ...week, revision: saves.length })),
        assignments: body.assignments.map(change => ({ id: change.id, revision: 1, assignment: change.assignment })),
      });
    }
    if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks: [], revision: 0 });
    if (path === '/api/solve') {
      const body = JSON.parse(options.body);
      solves.push(body);
      return response(200, { placed: body.blocks.filter(b => b.kind === 'locked'), unplaced: [], moves: [],
        explanations: [], failed_constraints: [], solve_ms: 1, complete: true });
    }
    return response(200, { theme: 'nocturne' });
  });
  const next = () => h.elements.get('setup-form').listeners.submit({ preventDefault() {} });
  h.elements.get('register-username').value = 'rookie';
  h.elements.get('register-password').value = 'a long enough password';
  await h.elements.get('register-form').listeners.submit({ preventDefault() {} });

  assert.equal(h.elements.get('setup-dialog').open, true);
  assert.equal(h.elements.get('setup-progress').textContent, 'Step 1 of 4');
  assert.equal(h.elements.get('setup-school-start').value, '08:00');
  assert.equal(h.elements.get('setup-school-end').value, '14:30');
  assert.equal(next(), true);

  assert.equal(next(), false);
  assert.equal(h.elements.get('setup-error').textContent, 'Pick the days you practice, or choose Skip this step.');
  h.elements.get('setup-sports-title').value = 'Soccer';
  h.elements.get('setup-sports-day-1').checked = true;
  h.elements.get('setup-sports-day-3').checked = true;
  assert.equal(next(), true);

  assert.equal(next(), false);
  assert.equal(h.elements.get('setup-error').textContent, 'Name the assignment, or choose Skip this step.');
  h.elements.get('setup-homework-title').value = 'Math worksheet';
  assert.equal(h.elements.get('setup-homework-due-date').value, '2026-09-11', 'due tomorrow by default');
  assert.equal(next(), true);

  assert.deepEqual(h.elements.get('setup-summary').children.map(item => item.textContent), [
    'School: Mon, Tue, Wed, Thu, Fri, 08:00–14:30',
    'Soccer: Tue, Thu, 15:30–17:00',
    'Math worksheet: 1 h, due Fri Sep 11, 21:00',
  ]);
  assert.equal(h.elements.get('setup-next').textContent, 'Add to my week and Solve');
  assert.equal(await next(), true);

  assert.equal(h.elements.get('setup-dialog').open, false);
  assert.equal(saves.length, 1);
  const [week] = saves[0].weeks;
  assert.deepEqual(week.blocks.map(b => [b.title, b.kind, b.category, b.days, b.start, b.duration_min, b.latest]), [
    ['School', 'locked', 'class', [0, 1, 2, 3, 4], '08:00', 390, null],
    ['Soccer', 'locked', 'exercise', [1, 3], '15:30', 90, null],
    ['Math worksheet', 'flexible', 'assignments', [3, 4], null, 60, null],
  ]);
  // The homework is an assignment with an exact due time; the week holds its work session.
  assert.equal(saves[0].assignments.length, 1);
  const { id, assignment, revision } = saves[0].assignments[0];
  assert.match(id, /^hw-/);
  assert.equal(week.blocks[2].assignment_id, id);
  assert.equal(revision, 0);
  const { id: bodyId, ...fields } = assignment;
  assert.equal(bodyId, id);
  assert.deepEqual(fields, {
    title: 'Math worksheet', course: null, category: 'assignments', priority: 3, energy: 'medium',
    spotify_url: null, due: '2026-09-11T21:00', estimate_min: 60, focus_minutes: 0, focus_sessions: 0,
    completed: false, completed_at: null,
  });
  assert.equal(h.run('dirtyAssignments.size'), 0);
  assert.equal(solves.length, 1);
  assert.equal(solves[0].week_start, MONDAY);
  assert.equal(h.elements.get('debug').hidden, false);
  assert.equal(h.elements.get('empty-week').hidden, true);
});

test('an empty week says so and setup can be skipped without adding anything', async () => {
  const h = harness();
  await h.login(1, []);
  assert.equal(h.elements.get('empty-week').hidden, false);
  assert.equal(Boolean(h.elements.get('setup-dialog').open), false, 'setup opens only for a new account or on request');

  h.elements.get('setup-open').listeners.click();
  assert.equal(h.elements.get('setup-dialog').open, true);
  let requests = 0;
  h.handle(async () => { requests += 1; return response(500, {}); });
  h.elements.get('setup-skip').listeners.click();
  h.elements.get('setup-back').listeners.click();
  assert.equal(h.elements.get('setup-progress').textContent, 'Step 1 of 4');
  for (let step = 0; step < 3; step += 1) h.elements.get('setup-skip').listeners.click();
  assert.equal(h.elements.get('setup-next').textContent, 'Finish');
  assert.equal(await h.elements.get('setup-form').listeners.submit({ preventDefault() {} }), false);
  assert.equal(requests, 0);
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(h.elements.get('empty-week').hidden, false);
  assert.match(h.elements.get('status').textContent, /Setup skipped/);
});

function deviceScheme(dark) {
  const listeners = [];
  const query = { matches: dark, addEventListener: (type, listener) => listeners.push(listener) };
  return {
    matchMedia: text => { assert.equal(text, '(prefers-color-scheme: dark)'); return query; },
    set(value) { query.matches = value; listeners.forEach(listener => listener({ matches: value })); },
  };
}

test('signed out, the theme follows the device and switches when the device does', async () => {
  const device = deviceScheme(true);
  const h = harness({ matchMedia: device.matchMedia });
  await tick();
  assert.equal(h.run('document.documentElement.dataset.theme'), 'nocturne');
  device.set(false);
  assert.equal(h.run('document.documentElement.dataset.theme'), 'slate');
});

test('an account on System follows the device until Light or Dark is chosen', async () => {
  const device = deviceScheme(false);
  const h = harness({ matchMedia: device.matchMedia });
  await tick();
  h.handle(async (path, options) => {
    if (path.startsWith('/api/weeks')) return response(200, { weeks: [] });
    if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks: [], revision: 0 });
    return response(200, options && options.method === 'PUT' ? JSON.parse(options.body) : { theme: 'system' });
  });
  await h.run("loadAccount({id:4,username:'student4'})");
  assert.equal(h.elements.get('theme').value, 'system');
  assert.equal(h.run('document.documentElement.dataset.theme'), 'slate');
  device.set(true);
  assert.equal(h.run('document.documentElement.dataset.theme'), 'nocturne');

  h.elements.get('theme').value = 'slate';
  await h.elements.get('theme').listeners.change();
  assert.equal(h.run('prefs.theme'), 'slate');
  assert.equal(h.run('document.documentElement.dataset.theme'), 'slate');
  device.set(false);
  device.set(true);
  assert.equal(h.run('document.documentElement.dataset.theme'), 'slate', 'a chosen theme must ignore the device');

  h.run('signedOut()');
  assert.equal(h.run('document.documentElement.dataset.theme'), 'nocturne', 'signing out follows the device again');
});

test('without a device preference the System theme is light', async () => {
  const h = harness();
  await tick();
  assert.equal(h.run('document.documentElement.dataset.theme'), 'slate');
});

// Stage 1: homework is an assignment that outlives a week; the week holds its work session.
const session = { ...task, assignment_id: 'hw-math' };
const mathAssignment = {
  id: 'hw-math', title: 'Math', course: null, category: null, priority: 3, energy: 'medium', spotify_url: null,
  due: '2026-09-11T21:00', estimate_min: 60, focus_minutes: 0, focus_sessions: 0, completed: false,
  completed_at: null, revision: 2, planned_min: 60, unplanned_min: 0,
};
const changesReply = (body, revision = 3) => response(200, {
  weeks: body.weeks.map(week => ({ ...week, revision: week.revision + 1 })),
  assignments: body.assignments.map(change => ({ id: change.id, revision, assignment: change.assignment })),
});

test('assignment edits save with their week in one change, and a week without any still uses PUT', async () => {
  const h = harness();
  await h.login(1, [session]);
  h.run(`assignments.set('hw-math', ${JSON.stringify(mathAssignment)})`);
  const calls = [];
  h.handle(async (path, options) => {
    const body = JSON.parse(options.body);
    calls.push({ path, body });
    if (path === '/api/changes') return changesReply(body);
    return response(200, { week_start: body.week_start, blocks: body.blocks, revision: body.revision + 1 });
  });

  h.run("putAssignment({ ...assignments.get('hw-math'), title: 'Algebra' })");
  assert.equal(await h.run('saveWeek()'), true);
  assert.equal(calls[0].path, '/api/changes');
  assert.deepEqual(calls[0].body.weeks.map(week => [week.week_start, week.revision]), [[MONDAY, 0]]);
  assert.deepEqual(calls[0].body.assignments.map(change => [change.id, change.revision, change.assignment.title]),
    [['hw-math', 2, 'Algebra']]);
  assert.equal('planned_min' in calls[0].body.assignments[0].assignment, false, 'only contract fields are sent');
  assert.equal(h.run("assignments.get('hw-math').revision"), 3);
  assert.equal(h.run('dirtyAssignments.size'), 0);

  assert.equal(await h.run('saveWeek()'), true);
  assert.equal(calls[1].path, '/api/week');
  assert.equal(h.run('weekState().revision'), 2);
});

test('Solve sends the week on screen, so the server can turn due dates into bounds', async () => {
  const h = harness();
  await h.login(1, [session]);
  let body;
  h.handle(async (_path, options) => {
    body = JSON.parse(options.body);
    return response(200, { placed: [], unplaced: [], moves: [], explanations: [], failed_constraints: [],
      solve_ms: 1, complete: true });
  });
  await h.run('solveWeek()');
  assert.equal(body.week_start, MONDAY);
  assert.equal(body.blocks[0].assignment_id, 'hw-math');
});

test('marking homework done finishes its assignment, and unmarking it reopens the assignment', async () => {
  const h = harness();
  await h.login(1, [session]);
  h.run(`assignments.set('hw-math', ${JSON.stringify(mathAssignment)})`);
  h.handle(async () => { throw new Error('Offline'); });

  assert.equal(h.run("toggleCompleted('homework')"), true);
  await tick();
  await tick();
  assert.equal(h.run("assignments.get('hw-math').completed"), true);
  assert.equal(h.run("assignments.get('hw-math').completed_at"), '2026-09-10T12:00');
  assert.equal(h.run("dirtyAssignments.has('hw-math')"), true);

  assert.equal(h.run("toggleCompleted('homework')"), true);
  await tick();
  await tick();
  assert.equal(h.run("assignments.get('hw-math').completed"), false);
  assert.equal(h.run("assignments.get('hw-math').completed_at"), null);
});

test('an import may carry assignment_id, but not together with an old weekday deadline', () => {
  const h = harness();
  assert.equal(h.run(`importBlockError(${JSON.stringify(session)}, 0)`), null);
  assert.equal(h.run(`importBlockError(${JSON.stringify({ ...session, latest: 'Friday 21:00' })}, 0)`),
    'Block 1 has both a deadline and an assignment.');
});

test('an expired session keeps unsaved assignment edits, for the same account only', async () => {
  const h = harness();
  await h.login(1, [session]);
  h.run(`assignments.set('hw-math', ${JSON.stringify(mathAssignment)})`);
  h.handle(async () => { throw new Error('Offline'); });
  h.run("putAssignment({ ...assignments.get('hw-math'), title: 'Algebra' })");
  assert.equal(await h.run('saveWeek()'), false);

  h.run('signedOut()');
  assert.equal(h.run('assignments.size'), 0);
  await h.login(2, []);
  assert.equal(h.run('dirtyAssignments.size'), 0, 'another account never receives them');
  await h.login(1, [session]);
  assert.equal(h.run("assignments.get('hw-math').title"), 'Algebra');
  assert.equal(h.run("dirtyAssignments.has('hw-math')"), true);
});

// Stage 1: Continuing lists homework that still needs time no session covers.
const openAssignment = (id, fields) => ({
  id, title: id, course: null, category: 'assignments', priority: 3, energy: 'medium', spotify_url: null,
  estimate_min: 60, focus_minutes: 0, focus_sessions: 0, completed: false, completed_at: null, revision: 1,
  planned_min: 0, unplanned_min: 0, ...fields,
});
const workSession = (id, minutes) => ({ id: 's-' + id, kind: 'flexible', title: id, duration_min: minutes, days: [3, 4], assignment_id: id });
const continuing = h => JSON.parse(h.run('JSON.stringify(continuingAssignments().map(entry => [entry.assignment.id, entry.minutes]))'));

test('Continuing lists homework that still needs time, counting sessions this week and in later weeks', async () => {
  const h = harness();
  const owned = [
    openAssignment('Quiz', { due: '2026-09-11T09:00', estimate_min: 60, planned_min: 60 }),
    openAssignment('Essay', { due: '2026-09-16T21:00', estimate_min: 180, focus_minutes: 30, planned_min: 60 }),
    openAssignment('Project', { due: '2026-09-20T23:59', estimate_min: 120, planned_min: 120 }),
    openAssignment('Lab', { due: '2026-09-08T21:00', estimate_min: 60 }),
    openAssignment('Poem', { due: '2026-09-18T12:00', completed: true, completed_at: '2026-09-09T10:00' }),
  ];
  await h.login(1, [workSession('Essay', 60), workSession('Quiz', 60)], [], owned);
  // Essay: 180 minus 30 focused minus the 60-minute session. Quiz is covered here, Project next
  // week, Lab was due Tuesday and Poem is finished.
  assert.deepEqual(continuing(h), [['Essay', 90]]);
  assert.equal(h.elements.get('continuing-section').hidden, false);
  const card = h.elements.get('continuing').children[0];
  assert.equal(card.children[0].textContent, 'Essay');
  assert.equal(card.children[1].textContent, h.run('formatDuration(90)') + ' not planned yet · due Wed Sep 16, 21:00');

  h.run('weekState().blocks[1].duration_min = 30');
  assert.deepEqual(continuing(h), [['Quiz', 30], ['Essay', 90]], 'a shorter session counts before it is saved');
});

test('Plan the rest here adds a session for the missing time on the days up to the due date', async () => {
  const h = harness();
  await h.login(1, [workSession('Essay', 60)], [], [
    openAssignment('Essay', { due: '2026-09-12T21:00', estimate_min: 150, planned_min: 60 }),
  ]);
  let saved;
  h.handle(async (path, options) => {
    assert.equal(path, '/api/week', 'no assignment changed, so the week saves alone');
    saved = JSON.parse(options.body);
    return response(200, { ...saved, revision: 1 });
  });
  h.elements.get('continuing').children[0].children[2].listeners.click();
  await tick();
  const added = saved.blocks[1];
  assert.deepEqual([added.kind, added.title, added.duration_min, added.days, added.assignment_id, added.latest],
    ['flexible', 'Essay', 90, [3, 4, 5], 'Essay', null]);
  assert.equal(h.elements.get('continuing-section').hidden, true);
  assert.deepEqual(continuing(h), []);
});

test('a later week lists the homework with days from Monday to the due day, and an earlier week lists nothing', async () => {
  const h = harness();
  await h.login(1, [], [], [openAssignment('Essay', { due: '2026-09-16T21:00', estimate_min: 120 })]);
  assert.deepEqual(continuing(h), [['Essay', 120]]);
  assert.equal(await h.run("selectWeek('2026-08-31')"), true);
  assert.deepEqual(continuing(h), []);
  assert.equal(h.elements.get('continuing-section').hidden, true);
  assert.equal(await h.run("selectWeek('2026-09-14')"), true);
  assert.deepEqual(continuing(h), [['Essay', 120]]);

  let saved;
  h.handle(async (_path, options) => {
    saved = JSON.parse(options.body);
    return response(200, { ...saved, revision: 1 });
  });
  assert.equal(h.run("planRestHere('Essay')"), true);
  await tick();
  assert.equal(saved.week_start, '2026-09-14');
  assert.deepEqual(saved.blocks.map(block => [block.duration_min, block.days]), [[120, [0, 1, 2]]]);
});

test('Plan the rest here refuses a week that already holds 100 blocks and sends nothing', async () => {
  const h = harness();
  const full = Array.from({ length: 100 }, (_, i) => ({
    id: 'b' + i, kind: 'locked', title: 'Block', duration_min: 15, days: [0], start: '06:00',
  }));
  await h.login(1, full, [], [openAssignment('Essay', { due: '2026-09-16T21:00', estimate_min: 120 })]);
  const sent = h.requests.length;
  assert.equal(h.run("planRestHere('Essay')"), false);
  assert.equal(h.requests.length, sent);
  assert.equal(h.run('weekState().blocks.length'), 100);
  assert.equal(h.run('statusEl.textContent'), 'This week already has 100 blocks. Remove one before planning more here.');
});

test('homework added this week joins Continuing only when it needs more time than its sessions', async () => {
  const h = harness();
  await h.login(1, [], [], []);
  h.run(`weekState().blocks.push(attachAssignment(
    { id: 's1', kind: 'flexible', title: 'Essay', duration_min: 60, days: [3, 4] },
    { assignmentId: null, dueDate: '2026-09-12', dueTime: '21:00' }))`);
  const id = h.run('weekState().blocks[0].assignment_id');
  assert.deepEqual(continuing(h), []);
  h.run(`putAssignment({ ...assignments.get(${JSON.stringify(id)}), estimate_min: 90 })`);
  assert.deepEqual(continuing(h), [[id, 30]]);
});

// Stage 1: undo and redo.
const weekdaySchool = { id: 'school', kind: 'locked', title: 'School', duration_min: 390, days: [0, 1, 2, 3, 4], start: '08:00', priority: 1, energy: 'medium' };
const inPage = (h, code) => JSON.parse(h.run(`JSON.stringify(${code})`));

/** A server that accepts every write and counts revisions up, recording what it was sent. */
function fakeServer(h) {
  const calls = [];
  h.handle(async (path, options = {}) => {
    const method = options.method || 'GET';
    const body = options.body ? JSON.parse(options.body) : null;
    calls.push({ method, path, body });
    if (path === '/api/changes') return changesReply(body);
    if (path === '/api/solve') {
      return response(200, { placed: [], unplaced: [], moves: [], explanations: [], failed_constraints: [], solve_ms: 1, complete: true });
    }
    if (method === 'PUT') return response(200, { ...body, revision: body.revision + 1 });
    if (method === 'DELETE') return response(200, { changed_weeks: [], removed_sessions: {} });
    return response(404, { detail: `unexpected ${method} ${path}` });
  });
  return calls;
}

async function settle() {
  await tick();
  await tick();
}

test('Undo after a delete puts the block back with one week save, and Redo deletes it again', async () => {
  const h = harness();
  await h.login(1, [weekdaySchool]);
  const calls = fakeServer(h);
  assert.equal(h.elements.get('undo').hidden, true);
  assert.equal(h.run("deleteBlockById('school')"), true);
  await settle();
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(h.elements.get('undo').hidden, false);
  assert.equal(h.run('statusEl.textContent'), 'Deleted School. Undo brings it back.');

  assert.equal(await h.run('undo()'), true);
  assert.deepEqual(calls.map(call => [call.method, call.path, call.body.revision]), [['PUT', '/api/week', 0], ['PUT', '/api/week', 1]]);
  assert.deepEqual(calls[1].body.blocks.map(block => block.id), ['school']);
  assert.equal(h.run('weekState().blocks[0].id'), 'school');
  assert.equal(h.run('statusEl.textContent'), 'Undid deleting School.');
  assert.equal(h.elements.get('redo').hidden, false);

  assert.equal(await h.run('redo()'), true);
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(calls.at(-1).body.revision, 2);
});

test('Undo after Clear week restores every block, and a new edit clears Redo', async () => {
  const h = harness();
  await h.login(1, [weekdaySchool, task]);
  fakeServer(h);
  h.elements.get('new-week').listeners.click();
  await settle();
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(await h.run('undo()'), true);
  assert.deepEqual(inPage(h, 'weekState().blocks.map(block => block.id)'), ['school', 'homework']);
  assert.equal(h.elements.get('redo').hidden, false);

  assert.equal(h.run("deleteBlockById('homework')"), true);
  await settle();
  assert.equal(h.run('redoSteps.length'), 0);
  assert.equal(h.elements.get('redo').hidden, true);
});

test('Undo after a missed-day replan brings the day back as it was', async () => {
  const h = harness();
  await h.login(1, [weekdaySchool]);
  const calls = fakeServer(h);
  h.run('weekState().trace = { placed: [], unplaced: [], moves: [], explanations: [] }');
  await h.run("recoverMissedOccurrence('school', 1)");
  assert.deepEqual(inPage(h, 'weekState().blocks[0].missed_days'), [1]);
  assert.equal(await h.run('undo()'), true);
  assert.deepEqual(calls.at(-1).body.blocks[0].missed_days || [], []);
  assert.equal(h.run('statusEl.textContent'), 'Undid the replan.');
});

test('Undo after deleting a whole homework re-creates it and puts back every removed session in one change', async () => {
  const h = harness();
  const math = openAssignment('hw-math', { title: 'Math', due: '2026-09-16T21:00', estimate_min: 120, revision: 4 });
  const here = { id: 's-here', kind: 'flexible', title: 'Math', duration_min: 60, days: [3], assignment_id: 'hw-math' };
  const nextWeek = { id: 's-next', kind: 'flexible', title: 'Math', duration_min: 60, days: [0], assignment_id: 'hw-math' };
  const soccer = { id: 'soccer', kind: 'locked', title: 'Soccer', duration_min: 60, days: [1], start: '16:00' };
  await h.login(1, [weekdaySchool, here], [], [math]);
  const calls = [];
  h.handle(async (path, options = {}) => {
    const method = options.method || 'GET';
    const body = options.body ? JSON.parse(options.body) : null;
    calls.push({ method, path, body });
    if (method === 'DELETE') {
      return response(200, {
        changed_weeks: [{ week_start: MONDAY, revision: 1 }, { week_start: '2026-09-14', revision: 8 }],
        removed_sessions: { [MONDAY]: [here], '2026-09-14': [nextWeek] },
      });
    }
    if (path === '/api/week?week_start=2026-09-14') return response(200, { week_start: '2026-09-14', blocks: [soccer], revision: 8 });
    if (path === '/api/changes') return changesReply(body);
    return response(404, { detail: `unexpected ${method} ${path}` });
  });

  assert.equal(h.run("deleteBlockById('s-here')"), true);
  assert.equal(h.elements.get('delete-dialog').open, true);
  assert.equal(calls.length, 0, 'nothing is deleted before the student chooses');
  h.elements.get('delete-assignment').listeners.click();
  await settle();
  assert.equal(calls[0].path, '/api/assignments/hw-math?revision=4');
  assert.equal(h.run("assignments.has('hw-math')"), false);
  assert.deepEqual(inPage(h, 'weekState().blocks.map(block => block.id)'), ['school']);
  assert.equal(h.run('weekState().revision'), 1);

  assert.equal(await h.run('undo()'), true);
  const change = calls.at(-1);
  assert.equal(change.path, '/api/changes');
  assert.deepEqual(change.body.assignments.map(item => [item.id, item.revision, item.assignment.title]), [['hw-math', 0, 'Math']]);
  assert.deepEqual(change.body.weeks.map(week => [week.week_start, week.revision, week.blocks.map(block => block.id)]), [
    [MONDAY, 1, ['school', 's-here']],
    ['2026-09-14', 8, ['soccer', 's-next']],
  ]);
  assert.equal(h.run("assignments.get('hw-math').revision"), 3);
  assert.deepEqual(inPage(h, 'weekState().blocks.map(block => block.id)'), ['school', 's-here']);
});

test('an undo refused with 409 stores nothing, keeps the step and shows the conflict actions', async () => {
  const h = harness();
  await h.login(1, [weekdaySchool]);
  fakeServer(h);
  h.run("deleteBlockById('school')");
  await settle();
  h.handle(async () => response(409, { detail: 'This week changed elsewhere.' }));
  assert.equal(await h.run('undo()'), false);
  assert.equal(h.run('undoSteps.length'), 1);
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(h.run('weekState().conflict'), true);
  assert.equal(h.elements.get('save-actions').hidden, false);
  assert.match(h.run('statusEl.textContent'), /^Could not undo deleting School: it changed on another device\./);
});

test('an older step for a week another device changed is skipped instead of overwriting the newer week', async () => {
  const h = harness();
  await h.login(1, [weekdaySchool]);
  fakeServer(h);
  h.run("deleteBlockById('school')");
  await settle();
  // Reload saved week finds revision 5, which this page never wrote.
  h.handle(async () => response(200, { week_start: MONDAY, blocks: [task], revision: 5 }));
  h.elements.get('reload-week').listeners.click();
  await settle();
  const sent = h.requests.length;
  assert.equal(await h.run('undo()'), false);
  assert.equal(h.requests.length, sent);
  assert.equal(h.run('undoSteps.length'), 0);
  assert.equal(h.run('statusEl.textContent'), 'Undo skipped deleting School: it changed on another device since.');
});

test('Undo after adding homework saves the week without the session, then deletes the empty assignment', async () => {
  const h = harness();
  await h.login(1, [weekdaySchool]);
  const calls = fakeServer(h);
  h.run(`weekState().blocks.push(attachAssignment(
    { id: 's1', kind: 'flexible', title: 'Essay', duration_min: 60, days: [3, 4] },
    { assignmentId: null, dueDate: '2026-09-12', dueTime: '21:00' }))`);
  h.run('commitWeek()');
  await settle();
  assert.equal(calls[0].path, '/api/changes');
  const id = h.run('weekState().blocks[1].assignment_id');
  assert.equal(await h.run('undo()'), true);
  assert.deepEqual(calls.slice(1).map(call => [call.method, call.path]),
    [['PUT', '/api/week'], ['DELETE', `/api/assignments/${id}?revision=3`]]);
  assert.deepEqual(calls[1].body.blocks.map(block => block.id), ['school']);
  assert.equal(h.run(`assignments.has(${JSON.stringify(id)})`), false);
});

test('Undo of a homework edit keeps the focus minutes counted since', async () => {
  const h = harness();
  const math = openAssignment('hw-math', { title: 'Math', due: '2026-09-16T21:00', estimate_min: 120, revision: 2 });
  await h.login(1, [{ id: 's-here', kind: 'flexible', title: 'Math', duration_min: 60, days: [3], assignment_id: 'hw-math' }], [], [math]);
  const calls = fakeServer(h);
  h.run("putAssignment({ ...assignments.get('hw-math'), title: 'Algebra' })");
  h.run('commitWeek()');
  await settle();
  // A focus session is credited afterwards; that is progress, not an edit.
  h.run("putAssignment({ ...assignments.get('hw-math'), focus_minutes: 30, focus_sessions: 1 })");
  h.run('absorbIntoHistory()');
  assert.equal(await h.run('saveWeek()'), true);
  assert.equal(await h.run('undo()'), true);
  const restored = calls.at(-1);
  assert.equal(restored.path, '/api/assignments/hw-math');
  assert.deepEqual([restored.body.title, restored.body.focus_minutes, restored.body.focus_sessions, restored.body.revision],
    ['Math', 30, 1, 3]);
});

test('Ctrl+Z undoes, Ctrl+Shift+Z and Ctrl+Y redo, but not while typing in a field', async () => {
  const h = harness();
  await h.login(1, [weekdaySchool]);
  fakeServer(h);
  h.run("deleteBlockById('school')");
  await settle();
  const press = ({ key, ctrl = false, meta = false, shift = false, field = false }) => h.run(`handleHistoryKey({
    preventDefault() {}, target: ${field ? '{ closest: () => ({}) }' : 'null'}, key: ${JSON.stringify(key)},
    ctrlKey: ${ctrl}, metaKey: ${meta}, shiftKey: ${shift}, altKey: false })`);
  assert.equal(press({ key: 'z', ctrl: true, field: true }), false);
  assert.equal(h.run('undoSteps.length'), 1);
  assert.equal(press({ key: 'z', meta: true }), true);
  await settle();
  assert.equal(h.run('redoSteps.length'), 1);
  assert.equal(press({ key: 'Z', ctrl: true, shift: true }), true);
  await settle();
  assert.equal(h.run('undoSteps.length'), 1);
  assert.equal(press({ key: 'z', ctrl: true }), true);
  await settle();
  assert.equal(press({ key: 'y', ctrl: true }), true);
  await settle();
  assert.equal(h.run('weekState().blocks.length'), 0);
  assert.equal(press({ key: 'y', meta: true }), false, 'Cmd+Y is not redo');
});

test('history is cleared when another account signs in', async () => {
  const h = harness();
  await h.login(1, [weekdaySchool]);
  fakeServer(h);
  h.run("deleteBlockById('school')");
  await settle();
  assert.equal(h.run('undoSteps.length'), 1);
  await h.login(2, []);
  assert.equal(h.run('undoSteps.length + redoSteps.length'), 0);
  assert.equal(h.elements.get('undo').hidden, true);
});

test('repeating blocks offer Remove Tuesday only and Delete all days; a one-day block offers Delete', async () => {
  const h = harness();
  const dentist = { id: 'dentist', kind: 'locked', title: 'Dentist', duration_min: 60, days: [2], start: '15:00' };
  await h.login(1, [weekdaySchool, dentist]);
  h.run("openBlockEditor(weekState().blocks[0], 1, 'occurrence')");
  assert.equal(h.elements.get('form-delete').textContent, 'Remove Tuesday only');
  h.run("openBlockEditor(weekState().blocks[0], 1, 'series')");
  assert.equal(h.elements.get('form-delete').textContent, 'Delete all days');
  h.run("openBlockEditor(weekState().blocks[1], 2, 'occurrence')");
  assert.equal(h.elements.get('form-delete').textContent, 'Delete');
});

test('deleting homework asks first, and Remove this session keeps the homework', async () => {
  const h = harness();
  const math = openAssignment('hw-math', { title: 'Math', due: '2026-09-16T21:00', estimate_min: 120, planned_min: 60 });
  await h.login(1, [{ id: 's-here', kind: 'flexible', title: 'Math', duration_min: 60, days: [3], assignment_id: 'hw-math' }], [], [math]);
  const calls = fakeServer(h);
  assert.equal(h.run("deleteBlockById('s-here')"), true);
  assert.equal(h.elements.get('delete-dialog').open, true);
  assert.equal(calls.length, 0);
  h.elements.get('delete-session').listeners.click();
  await settle();
  assert.equal(h.elements.get('delete-dialog').open, false);
  assert.deepEqual(calls.map(call => [call.method, call.path]), [['PUT', '/api/week']]);
  assert.equal(h.run("assignments.has('hw-math')"), true);
  assert.equal(h.run('statusEl.textContent'), 'Removed this session of Math. The homework is kept. Undo brings the session back.');
});

test('deleting homework that was never saved asks for a save first, so Undo is never left pointing at nothing', async () => {
  const h = harness();
  await h.login(1, [weekdaySchool]);
  h.handle(async () => { throw new Error('Offline'); });
  h.run(`weekState().blocks.push(attachAssignment(
    { id: 's1', kind: 'flexible', title: 'Essay', duration_min: 60, days: [3, 4] },
    { assignmentId: null, dueDate: '2026-09-12', dueTime: '21:00' }))`);
  assert.equal(await h.run('commitWeek()'), false);
  const id = h.run('weekState().blocks[1].assignment_id');
  const sent = h.requests.length;
  assert.equal(await h.run(`deleteAssignmentEverywhere(${JSON.stringify(id)})`), false);
  assert.equal(h.requests.length, sent);
  assert.equal(h.run('weekState().blocks.length'), 2);
  assert.equal(h.run('statusEl.textContent'), 'Essay is not saved yet. Press Retry save, then delete it.');
});
