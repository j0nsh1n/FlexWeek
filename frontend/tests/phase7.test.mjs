process.env.TZ = 'America/Los_Angeles';

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const response = (status, data) => ({ status, ok: status < 400, json: async () => data });
const tick = () => new Promise(resolve => setImmediate(resolve));
const NOW = new Date(2026, 8, 10, 12, 0, 0);
const MONDAY = '2026-09-07';

class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [NOW.getTime()])); }
  static now() { return NOW.getTime(); }
}

const defaultPrefs = {
  theme: 'nocturne', reminders_enabled: false, reminder_lead_min: 5, reminder_sound: true,
  reminder_dnd_override: false, timer_work_min: 30, timer_break_min: 15,
  timer_long_break_min: 30, timer_long_break_every: 2, auto_split_pomodoro: false,
  default_spotify_url: null, alarms: [],
};

function harness() {
  const elements = new Map();
  const all = [];
  const opened = [];
  function connected() {
    const found = [];
    const seen = new Set();
    function visit(item) {
      if (seen.has(item)) return;
      seen.add(item); found.push(item); item.children.forEach(visit);
    }
    elements.forEach(visit);
    return found;
  }
  function element() {
    const classes = new Set();
    const item = {
      value: '', textContent: '', hidden: false, disabled: false, checked: false,
      dataset: {}, style: {}, children: [], listeners: {}, open: false,
      get className() { return [...classes].join(' '); },
      set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach(v => classes.add(v)); },
      classList: { add: v => classes.add(v), remove: v => classes.delete(v), contains: v => classes.has(v) },
      set innerHTML(_value) { this.children = []; }, get innerHTML() { return ''; },
      addEventListener(name, fn) { this.listeners[name] = fn; },
      appendChild(child) { this.children.push(child); child.parentNode = this; },
      replaceChildren() { this.children = []; },
      querySelector(selector) {
        return this.children.find(child => selector.split(',').some(part =>
          child.classList.contains(part.trim().replace(/^\./, '')))) || null;
      },
      querySelectorAll() { return []; }, closest() { return null; }, contains(node) { return this === node || this.children.includes(node); },
      getBoundingClientRect() { return { top: 0, bottom: 100, left: 0, right: 100, height: 100, width: 100 }; },
      setPointerCapture() {}, releasePointerCapture() {}, reset() {}, focus() {}, click() {}, scrollIntoView() {},
      showModal() { this.open = true; }, close() { this.open = false; },
      setAttribute(name) { if (name === 'open') this.open = true; },
      removeAttribute(name) { if (name === 'open') this.open = false; },
      remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(child => child !== this); },
    };
    all.push(item);
    return item;
  }
  for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], element());
  let handler = async () => response(401, { detail: 'Please sign in' });
  const requests = [];
  const context = vm.createContext({
    document: {
      getElementById: id => elements.get(id), documentElement: { dataset: { theme: 'nocturne' } },
      createElement: element, addEventListener() {}, hidden: false,
      querySelectorAll: selector => connected().filter(item => selector.split(',').some(part =>
        item.classList.contains(part.trim().replace(/^\./, '')))),
    },
    window: { addEventListener() {}, AudioContext: undefined, open: url => { opened.push(url); return {}; } },
    localStorage: { getItem() { return null; }, removeItem() {} },
    fetch: async (path, options) => { requests.push({ path, options }); return handler(path, options); },
    getComputedStyle: () => ({ getPropertyValue: () => '2.75rem' }),
    setTimeout, clearTimeout, setInterval, clearInterval, AbortController, structuredClone, console,
    confirm: () => true, Date: FixedDate, Notification: undefined, Blob,
    URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} },
  });
  vm.runInContext(source, context);
  return {
    elements, opened, requests, run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    async login(blocks = [], preferences = defaultPrefs) {
      await tick();
      handler = async path => {
        if (path.startsWith('/api/weeks')) return response(200, { weeks: [] });
        if (path.startsWith('/api/week')) return response(200, { week_start: MONDAY, blocks, revision: 0 });
        return response(200, preferences);
      };
      await vm.runInContext("loadAccount({id:1,username:'phase7'})", context);
    },
  };
}

test('pomodoro plan stays on the 15-minute grid and has no trailing break', () => {
  const h = harness();
  const plan = h.run('pomodoroPlan(75, 30, 15, 30, 2)');
  assert.deepEqual(JSON.parse(JSON.stringify(plan.segments)), [
    { role: 'work', duration_min: 30, index: 1 },
    { role: 'break', duration_min: 15, index: 1 },
    { role: 'work', duration_min: 30, index: 2 },
    { role: 'break', duration_min: 30, index: 2 },
    { role: 'work', duration_min: 15, index: 3 },
  ]);
  assert.equal(plan.total_min, 120);
  assert.match(h.run('pomodoroPlan(60, 25, 5, 15, 4).error'), /15-minute/);
});

test('manual split replaces one placed task atomically and persists metadata', async () => {
  const task = {
    id: 'essay', title: 'Essay', kind: 'flexible', duration_min: 60, days: [0],
    priority: 3, energy: 'medium', category: 'assignments', spotify_url: 'https://open.spotify.com/playlist/abc123',
  };
  const h = harness();
  await h.login([task]);
  h.run("weekState().trace = {placed:[{...weekState().blocks[0],days:[0],start:'16:00'}],unplaced:[]}");
  let saved;
  h.handle(async (path, options) => {
    assert.equal(path, '/api/week');
    saved = JSON.parse(options.body);
    return response(200, { ...saved, revision: 1 });
  });
  assert.equal(h.run('splitBlockIntoPomodoros("essay", 0)'), true);
  await tick();
  assert.equal(saved.blocks.length, 3);
  assert.deepEqual(saved.blocks.map(block => [block.pomodoro_role, block.start, block.duration_min]), [
    ['work', '16:00', 30], ['break', '16:30', 15], ['work', '16:45', 30],
  ]);
  assert.equal(saved.blocks[0].pomodoro_parent_id, 'essay');
  assert.equal(saved.blocks[0].spotify_url, task.spotify_url);
  assert.equal(saved.blocks[1].spotify_url, null);
});

test('focus completion credits once, persists the count, and completes the block', async () => {
  const block = { id: 'focus', title: 'Focus', kind: 'locked', duration_min: 30, days: [3], start: '12:00', priority: 3, energy: 'medium' };
  const h = harness();
  await h.login([block]);
  let puts = 0;
  h.handle(async (_path, options) => {
    puts += 1;
    const saved = JSON.parse(options.body);
    return response(200, { ...saved, revision: puts });
  });
  assert.equal(h.run('startFocus("focus", 3)'), true);
  await h.run('advanceFocusPhase(true)');
  assert.equal(h.run('weekState().blocks[0].focus_sessions'), 1);
  assert.equal(h.run('weekState().blocks[0].focus_minutes'), 30);
  assert.equal(h.run('weekState().blocks[0].completed'), true);
  assert.equal(puts, 1);
  assert.equal(h.run('focusState.phase'), 'break');
});

test('Now/Next uses half-open boundaries and gaps merge overlaps', () => {
  const h = harness();
  const blocks = [
    { id: 'a', title: 'A', kind: 'locked', duration_min: 60, days: [3], start: '10:00' },
    { id: 'b', title: 'B', kind: 'locked', duration_min: 30, days: [3], start: '11:00' },
    { id: 'c', title: 'C', kind: 'locked', duration_min: 30, days: [3], start: '10:30' },
  ];
  const result = h.run(`nowAndNext(${JSON.stringify(blocks)}, 3, 660)`);
  assert.equal(result.current.id, 'b');
  assert.equal(result.next, null);
  const gaps = h.run(`freeIntervals(${JSON.stringify(blocks)}, 3)`);
  assert.deepEqual(JSON.parse(JSON.stringify(gaps.slice(0, 2))), [
    { startMin: 360, endMin: 600 }, { startMin: 690, endMin: 1380 },
  ]);
});

test('alarms fire once, require dismissal, and snooze without losing configuration', async () => {
  const alarm = { id: 'noon', name: 'Noon', time: '12:00', days: [3], enabled: true, sound: 'spotify', spotify_url: 'https://open.spotify.com/track/abc123' };
  const h = harness();
  await h.login([], { ...defaultPrefs, alarms: [alarm] });
  h.run('lastAlarmCheck = Date.now() - 60000; checkAlarms(new Date())');
  assert.equal(h.run('activeAlarm.id'), 'noon');
  assert.equal(h.elements.get('alarm-dialog').open, true);
  assert.equal(h.opened.length, 1);
  h.run('checkAlarms(new Date())');
  assert.equal(h.run('alarmQueue.length'), 0);
  h.run('finishAlarm(true)');
  assert.equal(h.run('activeAlarm'), null);
  assert.equal(h.run('snoozedAlarms.has("noon")'), true);
});

test('Spotify links accept only official HTTPS shares and imports validate Phase 7 fields', () => {
  const h = harness();
  assert.equal(h.run('safeSpotifyUrl("javascript:alert(1)")'), '');
  assert.equal(h.run('safeSpotifyUrl("https://evil.example/track/abc")'), '');
  assert.equal(h.run('safeSpotifyUrl("https://open.spotify.com/track/abc123")'), 'https://open.spotify.com/track/abc123');
  const block = { id: 'x', title: 'X', kind: 'locked', duration_min: 30, days: [0], start: '08:00', focus_sessions: 2, focus_minutes: 60, pomodoro_role: 'work', pomodoro_index: 1, pomodoro_parent_id: 'parent' };
  assert.equal(h.run(`importBlockError(${JSON.stringify(block)}, 0)`), null);
  assert.match(h.run(`importBlockError(${JSON.stringify({ ...block, focus_sessions: -1 })}, 0)`), /focus_sessions/);
});
