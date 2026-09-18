process.env.TZ = 'America/Los_Angeles';

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';
import { runAppScripts } from './app-scripts.mjs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
const response = (status, data) => ({ status, ok: status < 400, json: async () => structuredClone(data) });
const tick = () => new Promise(resolve => setImmediate(resolve));
const MONDAY = '2026-09-07';
const NOW = new Date(2026, 8, 10, 12, 0, 0);

class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [NOW.getTime()])); }
  static now() { return NOW.getTime(); }
}

const defaultPrefs = {
  theme: 'nocturne', reminders_enabled: false, reminder_lead_min: 5, reminder_sound: true,
  reminder_dnd_override: false, timer_work_min: 30, timer_break_min: 15,
  timer_long_break_min: 30, timer_long_break_every: 4, auto_split_pomodoro: false,
  default_spotify_url: null, alarms: [], sidebar_width_px: null,
};

function harness(options = {}) {
  const stored = new Map(Object.entries(options.stored || {}));
  const elements = new Map();
  const all = [];
  const requests = [];
  const audio = { contexts: 0, gains: [], oscillators: 0 };
  let notificationRequests = 0;

  function matches(item, selector) {
    if (selector === '[data-timer-preset]') return item.dataset.timerPreset !== undefined;
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
    const style = {
      setProperty(name, value) { this[name] = value; },
      removeProperty(name) { delete this[name]; },
    };
    const item = {
      value: '', textContent: '', hidden: false, disabled: false, checked: false, open: false,
      dataset: {}, style, children: [], listeners: {},
      get className() { return [...classes].join(' '); },
      set className(value) { classes.clear(); String(value).split(/\s+/).filter(Boolean).forEach(v => classes.add(v)); },
      classList: { add: v => classes.add(v), remove: v => classes.delete(v), contains: v => classes.has(v) },
      set innerHTML(_value) { this.children = []; }, get innerHTML() { return ''; },
      addEventListener(name, fn) { this.listeners[name] = fn; },
      removeEventListener(name) { delete this.listeners[name]; },
      appendChild(child) { this.children.push(child); child.parentNode = this; },
      replaceChildren(...children) { this.children = children; },
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

  class AudioContext {
    constructor() { audio.contexts += 1; this.currentTime = 1; this.destination = {}; }
    createOscillator() {
      audio.oscillators += 1;
      return { type: '', frequency: { value: 0 }, connect() {}, start() {}, stop() {} };
    }
    createGain() {
      const gain = { value: 0 };
      audio.gains.push(gain);
      return { gain, connect() {} };
    }
  }
  function FakeNotification() {}
  FakeNotification.permission = 'default';
  FakeNotification.requestPermission = async () => { notificationRequests += 1; return 'denied'; };

  let handler = async () => response(401, { detail: 'Please sign in' });
  const context = vm.createContext({
    document: {
      getElementById: id => elements.get(id), documentElement: { dataset: { theme: 'nocturne' } },
      createElement: element, addEventListener() {}, hidden: false,
      querySelectorAll: selector => connected().filter(item => selector.split(',').some(part => matches(item, part.trim()))),
    },
    window: { addEventListener() {}, AudioContext, open: () => ({}) },
    localStorage: {
      getItem: key => (stored.has(key) ? stored.get(key) : null),
      setItem: (key, value) => stored.set(key, String(value)),
      removeItem: key => stored.delete(key),
    },
    sessionStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
    fetch: async (path, request) => { requests.push({ path, request }); return handler(path, request); },
    getComputedStyle: () => ({ getPropertyValue: () => '2.75rem' }),
    matchMedia: options.matchMedia || (() => ({ matches: false, addEventListener() {} })),
    setTimeout, clearTimeout, setInterval, clearInterval, AbortController, structuredClone, console,
    confirm: () => true, Date: FixedDate, Notification: FakeNotification,
    crypto: globalThis.crypto, TextEncoder, Blob,
    URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} },
  });
  runAppScripts(vm, context);
  return {
    elements, requests, audio,
    run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    notificationRequests: () => notificationRequests,
    async login(preferences = defaultPrefs, blocks = []) {
      await tick();
      handler = async path => {
        if (path.startsWith('/api/assignments')) return response(200, { assignments: [] });
        if (path.startsWith('/api/weeks')) return response(200, { weeks: [] });
        if (path.startsWith('/api/week')) return response(200, { week_start: MONDAY, blocks, revision: 0 });
        if (path === '/api/preferences') return response(200, preferences);
        return response(404, { detail: 'Unexpected request ' + path });
      };
      await vm.runInContext("loadAccount({id:1,username:'comfort'})", context);
    },
  };
}

test('settings expose four expandable groups and desktop/web limits without flattening the page', () => {
  const summaries = Array.from(html.matchAll(/<summary>(Appearance|Focus|Notifications|Account)<\/summary>/g), match => match[1]);
  assert.deepEqual(summaries, ['Appearance', 'Focus', 'Notifications', 'Account']);
  for (const id of ['pref-alert-volume', 'pref-end-chime', 'pref-tray-notifications', 'pref-start-at-login',
    'pref-preferred-view', 'timer-preview', 'test-reminder', 'preview-alert', 'sidebar-toggle', 'sidebar-resizer']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
});

test('Motion sits with the account look settings, and Customize is hidden on a phone', () => {
  const appearance = html.slice(html.indexOf('<summary>Appearance</summary>'), html.indexOf('<summary>Focus</summary>'));
  assert.doesNotMatch(appearance, /This device only/);
  assert.match(appearance, /id="pref-theme"/);
  assert.match(appearance, /id="pref-motion"/);
  assert.match(appearance, /id="appearance-customize"/);
  assert.match(appearance, /id="pref-accent"/);
  assert.match(appearance, /id="pref-accent-chips"/);
  const customize = appearance.slice(appearance.indexOf('id="appearance-customize"'));
  assert.match(customize, /id="pref-accent"/);
  assert.doesNotMatch(customize, /id="pref-motion"/);
  assert.match(css, /@media \(max-width: 800px\)[\s\S]*?#appearance-customize\s*\{\s*display:\s*none;/);
});

test('a saved collapsed desktop sidebar returns to the single-column phone layout', () => {
  assert.match(css, /@media \(max-width: 800px\)[\s\S]*?\.layout\[data-sidebar-collapsed="true"\]\s*\{\s*grid-template-columns:\s*1fr;/);
  assert.match(css, /\.layout\[data-sidebar-collapsed="true"\] \.side\s*\{\s*display:\s*block;/);
});

test('comfort preferences restore the chosen view and sidebar, then remain in the save payload', async () => {
  const h = harness();
  await h.login({
    ...defaultPrefs, alert_volume: 35, end_chime: true, tray_notifications: false,
    start_at_login: true, preferred_view: 'day', sidebar_collapsed: true, sidebar_width_px: 480,
  });
  assert.equal(h.run('plannerView'), 'day');
  assert.equal(h.elements.get('pref-alert-volume-value').textContent, '35%');
  assert.equal(h.elements.get('planner').dataset.sidebarCollapsed, 'true');
  assert.equal(h.elements.get('planner').style['--sidebar-width'], '480px');
  assert.equal(h.elements.get('sidebar-toggle').ariaExpanded, 'false');
  const payload = JSON.parse(h.run('JSON.stringify(preferencesPayload())'));
  assert.deepEqual(Object.fromEntries(Object.keys(payload).filter(key => key.startsWith('sidebar_') ||
    ['alert_volume', 'end_chime', 'tray_notifications', 'start_at_login', 'preferred_view'].includes(key))
    .map(key => [key, payload[key]])), {
    alert_volume: 35, end_chime: true, tray_notifications: false, start_at_login: true,
    preferred_view: 'day', sidebar_collapsed: true, sidebar_width_px: 480,
  });
});

test('the backend null sidebar width stays null so an unchanged Settings save is valid', async () => {
  const h = harness();
  await h.login();
  assert.equal(h.run('prefs.sidebar_width_px'), null);
  assert.equal(h.run('readComfortEdit().sidebar_width_px'), null);
  assert.equal(JSON.parse(h.run('JSON.stringify(preferencesPayload())')).sidebar_width_px, null);
  assert.equal(h.run('clampComfort("", 1, 180, 30)'), 30);
});

test('timer preview explains rounding and requires the student to apply it before auto-split can save', async () => {
  const h = harness();
  await h.login();
  h.elements.get('pref-timer-work').value = '25';
  h.elements.get('pref-timer-break').value = '5';
  h.elements.get('pref-timer-long-break').value = '30';
  h.elements.get('pref-timer-cadence').value = '4';
  h.elements.get('timer-preview-duration').value = '90';
  h.handle(async (path, request) => {
    assert.equal(path, '/api/timer-split-preview');
    assert.deepEqual(JSON.parse(request.body), {
      duration_min: 90, timer_work_min: 25, timer_break_min: 5,
      timer_long_break_min: 30, timer_long_break_every: 4,
    });
    return response(200, {
      timer_work_min: 30, timer_break_min: 15, timer_long_break_min: 30,
      timer_long_break_every: 4, rounded: true,
      message: 'Work length 25 minutes becomes 30 on the 15-minute grid. Break length 5 minutes becomes 15 on the 15-minute grid.',
      segments: [{ role: 'work', duration_min: 30, index: 1 }, { role: 'break', duration_min: 15, index: 1 }, { role: 'work', duration_min: 30, index: 2 }, { role: 'break', duration_min: 15, index: 2 }, { role: 'work', duration_min: 30, index: 3 }],
      total_min: 120,
    });
  });
  await h.run('previewTimerSplit()');
  assert.equal(h.elements.get('timer-preview-result').hidden, false);
  assert.match(h.elements.get('timer-preview-message').textContent, /25 minutes becomes 30/);
  assert.match(h.elements.get('timer-preview-segments').textContent, /120 min on the calendar/);
  assert.equal(h.elements.get('timer-use-rounded').hidden, false);
  const saveProblem = await h.run('prepareComfortSave({...timerEdit(), auto_split_pomodoro:true})');
  assert.match(saveProblem, /Use rounded times/);
  h.run('useRoundedTimerPreview()');
  assert.equal(h.elements.get('pref-timer-work').value, '30');
  assert.equal(h.elements.get('pref-timer-break').value, '15');
});

test('preset and reminder reference data load from the authenticated Stage 5 routes', async () => {
  const h = harness();
  await h.login();
  h.handle(async path => {
    if (path === '/api/timer-presets') return response(200, { presets: [{
      id: 'study', label: 'Study', timer_work_min: 45, timer_break_min: 15,
      timer_long_break_min: 30, timer_long_break_every: 4,
    }] });
    if (path === '/api/reminder-limits') return response(200, {
      web_open: 'Web needs an open tab.', desktop_background: 'Desktop can use the tray.',
      spotify: 'Spotify is best-effort.', duplicate: 'Each start alerts once.',
    });
    return response(404, { detail: path });
  });
  await h.run('prepareComfortAccount()');
  assert.deepEqual(h.requests.slice(-2).map(item => item.path), ['/api/timer-presets', '/api/reminder-limits']);
  assert.equal(h.elements.get('timer-presets').children[0].textContent, 'Study');
  assert.deepEqual(h.elements.get('reminder-limits').children.map(item => item.textContent), [
    'Web needs an open tab.', 'Desktop can use the tray.', 'Spotify is best-effort.', 'Each start alerts once.',
  ]);
  h.elements.get('timer-presets').children[0].listeners.click();
  assert.equal(h.elements.get('pref-timer-work').value, '45');
});

test('a split preview that returns after sign-out cannot repopulate private settings', async () => {
  const h = harness();
  await h.login();
  let release;
  const held = new Promise(resolve => { release = resolve; });
  h.handle(async path => {
    assert.equal(path, '/api/timer-split-preview');
    await held;
    return response(200, {
      timer_work_min: 30, timer_break_min: 15, timer_long_break_min: 30,
      timer_long_break_every: 4, rounded: false, message: '', segments: [], total_min: 0,
    });
  });
  const pending = h.run('previewTimerSplit()');
  await tick();
  h.run('signedOut()');
  release();
  await pending;
  assert.equal(h.elements.get('timer-preview-result').hidden, true);
  assert.equal(h.run('lastSplitPreview'), null);
});

test('saving Settings sends every comfort choice in the existing flat preferences object', async () => {
  const h = harness();
  await h.login();
  h.elements.get('pref-alert-volume').value = '62';
  h.elements.get('pref-end-chime').checked = true;
  h.elements.get('pref-tray-notifications').checked = false;
  h.elements.get('pref-start-at-login').checked = true;
  h.elements.get('pref-preferred-view').value = 'week';
  let saved;
  h.handle(async (path, request) => {
    assert.equal(path, '/api/preferences');
    saved = JSON.parse(request.body);
    return response(200, saved);
  });
  await h.elements.get('prefs-form').listeners.submit({
    submitter: { value: 'save' }, preventDefault() {},
  });
  assert.deepEqual(Object.fromEntries(['alert_volume', 'end_chime', 'tray_notifications', 'start_at_login', 'preferred_view']
    .map(key => [key, saved[key]])), {
    alert_volume: 62, end_chime: true, tray_notifications: false,
    start_at_login: true, preferred_view: 'week',
  });
});

test('Motion is stored on the account and a copy stays on this device', async () => {
  const h = harness();
  await h.login();
  assert.equal(h.elements.get('pref-motion').value, 'normal');
  h.elements.get('pref-motion').value = 'extra';
  h.elements.get('pref-motion').listeners.change();
  assert.equal(h.run('document.documentElement.dataset.motion'), 'extra');
  const payload = JSON.parse(h.run('JSON.stringify(preferencesPayload())'));
  assert.equal(payload.motion, 'extra');
});

test('an unknown stored motion level falls back to Normal rather than breaking', async () => {
  const h = harness();
  await h.login();
  assert.equal(h.run('applyMotion("sideways")'), 'normal');
  assert.equal(h.run('document.documentElement.dataset.motion'), 'normal');
  assert.equal(h.run('applyMotion("off")'), 'off');
});

test('Look and Text size sit up front, the other look knobs inside Customize', () => {
  const appearance = html.slice(html.indexOf('<summary>Appearance</summary>'), html.indexOf('<summary>Focus</summary>'));
  const customize = appearance.slice(appearance.indexOf('id="appearance-customize"'));
  const front = appearance.slice(0, appearance.indexOf('id="appearance-customize"'));
  assert.match(front, /id="pref-theme"/);
  assert.match(front, /id="pref-text"/);
  assert.doesNotMatch(front, /id="pref-preset"/);
  for (const knob of ['surface', 'corners', 'depth', 'font', 'blocks', 'density']) {
    assert.match(customize, new RegExp(`id="pref-${knob}"`), `${knob} belongs inside Customize`);
    assert.doesNotMatch(front, new RegExp(`id="pref-${knob}"`));
  }
});

test('the preset and look knobs change this device only and never enter the account payload', async () => {
  const h = harness();
  await h.login();
  const before = h.requests.length;
  h.elements.get('pref-theme').value = 'terminal';
  h.elements.get('pref-theme').listeners.change();
  // theme.js and motion.js write their own attributes beside these; only the look keys are under test.
  const LOOK_KEYS = ['preset', 'surface', 'corners', 'depth', 'font', 'blocks', 'density', 'text'];
  const root = JSON.parse(h.run('JSON.stringify(document.documentElement.dataset)'));
  assert.deepEqual(Object.fromEntries(LOOK_KEYS.filter(key => key in root).map(key => [key, root[key]])), {
    preset: 'terminal', surface: 'flat', corners: 'sharp', depth: 'flat',
    font: 'mono', blocks: 'outlined', density: 'compact',
  });
  assert.equal(h.requests.length, before, 'changing the look must not talk to the server');
  // Two builders reach /api/preferences: the layout save uses preferencesPayload(), and the
  // Save button submits the form, which spreads readComfortEdit(). Both must stay clean.
  const leaked = ['preset', 'surface', 'corners', 'depth', 'font', 'blocks', 'density', 'text', 'look'];
  const layout = JSON.parse(h.run('JSON.stringify(preferencesPayload())'));
  for (const key of leaked) assert.ok(!(key in layout), `${key} leaks through the layout save`);
  let saved;
  h.handle(async (path, request) => {
    assert.equal(path, '/api/preferences');
    saved = JSON.parse(request.body);
    return response(200, saved);
  });
  await h.elements.get('prefs-form').listeners.submit({ submitter: { value: 'save' }, preventDefault() {} });
  assert.ok(saved, 'the Save button did not send preferences');
  for (const key of leaked) assert.ok(!(key in saved), `${key} leaks through the Save button`);
});

test('a knob set by hand stays when a look is chosen', async () => {
  const h = harness();
  await h.login();
  h.elements.get('pref-corners').value = 'pill';
  h.elements.get('pref-corners').listeners.change();
  assert.equal(h.run('document.documentElement.dataset.corners'), 'pill');
  h.elements.get('pref-theme').value = 'terminal';
  h.elements.get('pref-theme').listeners.change();
  assert.equal(h.run('document.documentElement.dataset.corners'), 'pill');
  assert.equal(h.run('document.documentElement.dataset.font'), 'mono');
  h.elements.get('pref-depth').value = 'hard';
  h.elements.get('pref-depth').listeners.change();
  assert.equal(h.run('document.documentElement.dataset.depth'), 'hard');
  assert.equal(h.run('document.documentElement.dataset.font'), 'mono', 'other knobs keep the preset value');
  assert.equal(h.elements.get('pref-depth').value, 'hard');
  assert.equal(h.elements.get('pref-corners').value, 'pill');
});

test('a stored look is applied before the body paints, and a bad one falls back to the pack', async () => {
  const kept = harness({ stored: { 'flexweek-look': JSON.stringify({ preset: 'default', knobs: { font: 'serif', text: 'large' } }) } });
  assert.equal(kept.run('document.documentElement.dataset.font'), 'serif');
  assert.equal(kept.run('document.documentElement.dataset.text'), 'large');
  assert.equal(kept.run('document.documentElement.dataset.preset'), undefined);
  await kept.login();
  assert.equal(kept.elements.get('pref-font').value, 'serif');
  assert.equal(kept.elements.get('pref-text').value, 'large');

  const broken = harness({ stored: { 'flexweek-look': '{not json' } });
  const brokenRoot = JSON.parse(broken.run('JSON.stringify(document.documentElement.dataset)'));
  for (const key of ['preset', 'surface', 'corners', 'depth', 'font', 'blocks', 'density', 'text']) {
    assert.ok(!(key in brokenRoot), `${key} leaked from an unreadable stored look`);
  }
  const unknown = harness({ stored: { 'flexweek-look': JSON.stringify({ preset: 'neon', knobs: { corners: 'hexagonal', font: 'mono' } }) } });
  assert.equal(unknown.run('document.documentElement.dataset.preset'), undefined);
  assert.equal(unknown.run('document.documentElement.dataset.corners'), undefined);
  assert.equal(unknown.run('document.documentElement.dataset.font'), 'mono', 'a valid knob beside a bad one still applies');
});

test('a knob at its default leaves no attribute behind', async () => {
  const h = harness();
  await h.login();
  h.elements.get('pref-density').value = 'compact';
  h.elements.get('pref-density').listeners.change();
  assert.equal(h.run('document.documentElement.dataset.density'), 'compact');
  h.elements.get('pref-density').value = 'comfortable';
  h.elements.get('pref-density').listeners.change();
  assert.equal(h.run('document.documentElement.dataset.density'), undefined);
});

test('alert previews stay local, honor unsaved volume, and never consume a reminder key', async () => {
  const h = harness();
  await h.login();
  const beforeRequests = h.requests.length;
  h.elements.get('pref-reminder-sound').checked = true;
  h.elements.get('pref-alert-volume').value = '50';
  h.run('previewComfortAlert("reminder")');
  assert.equal(h.requests.length, beforeRequests);
  assert.equal(h.notificationRequests(), 0);
  assert.equal(h.run('firedReminders.size'), 0);
  assert.equal(h.audio.oscillators, 2);
  assert.equal(h.audio.gains[0].value, 0.02);
  h.elements.get('pref-alert-volume').value = '0';
  h.run('previewComfortAlert("alert")');
  assert.equal(h.audio.oscillators, 2, 'zero volume must not create or start audio');
  assert.match(h.elements.get('reminder-toast').textContent, /Preview alert/);
});

test('focus transitions chime only when both sound and the optional end chime are enabled', async () => {
  const h = harness();
  const block = { id: 'focus', title: 'Essay', kind: 'locked', duration_min: 30, days: [3], start: '12:00' };
  await h.login(defaultPrefs, [block]);
  assert.equal(h.run('startFocus("focus", 3)'), true);
  h.run('prefs.end_chime = false; prefs.reminder_sound = true; setFocusPhase("break")');
  assert.equal(h.audio.oscillators, 0);
  h.run('prefs.end_chime = true; prefs.reminder_sound = false; setFocusPhase("work")');
  assert.equal(h.audio.oscillators, 0);
  h.run('prefs.end_chime = true; prefs.reminder_sound = true; setFocusPhase("break")');
  assert.equal(h.audio.oscillators, 1);
});

test('sidebar actions clamp width, persist collapse, and coalesce through the preference endpoint', async () => {
  const h = harness();
  await h.login();
  const saved = [];
  h.handle(async (path, request) => {
    assert.equal(path, '/api/preferences');
    const body = JSON.parse(request.body);
    saved.push(body);
    return response(200, body);
  });
  h.run('toggleSidebar()');
  await tick(); await tick();
  assert.equal(h.elements.get('planner').dataset.sidebarCollapsed, 'true');
  assert.equal(saved.at(-1).sidebar_collapsed, true);
  await h.run('setSidebarWidth(900, false); saveComfortLayout()');
  assert.equal(h.elements.get('planner').style['--sidebar-width'], '640px');
  assert.equal(saved.at(-1).sidebar_width_px, 640);
  assert.equal(h.elements.get('sidebar-resizer').ariaValueNow, '640');
});

test('Settings waits for an in-flight layout write so the older payload cannot land last', async () => {
  const h = harness();
  await h.login();
  let releaseLayout;
  const held = new Promise(resolve => { releaseLayout = resolve; });
  const writes = [];
  h.handle(async (path, request) => {
    assert.equal(path, '/api/preferences');
    const body = JSON.parse(request.body);
    writes.push(body);
    if (writes.length === 1) await held;
    return response(200, body);
  });
  h.run('rememberPlannerView("day")');
  await tick();
  h.elements.get('pref-alert-volume').value = '55';
  const formSave = h.elements.get('prefs-form').listeners.submit({
    submitter: { value: 'save' }, preventDefault() {},
  });
  await tick();
  assert.equal(writes.length, 1);
  releaseLayout();
  await formSave;
  assert.equal(writes.length, 2);
  assert.equal(writes[0].preferred_view, 'day');
  assert.equal(writes[1].preferred_view, 'day');
  assert.equal(writes[1].alert_volume, 55);
});

test('picking a pack applies its look and default motion together', async () => {
  const h = harness();
  await h.login();
  h.handle(async (path, request) => {
    if (path !== '/api/preferences') return response(404, { detail: path });
    return response(200, JSON.parse(request.body));
  });
  h.elements.get('theme').value = 'light-frost';
  await h.elements.get('theme').listeners.change();
  assert.equal(h.run('document.documentElement.dataset.pack'), 'light-frost');
  assert.equal(h.run('document.documentElement.dataset.theme'), 'light-frost');
  assert.equal(h.run('prefs.theme'), 'slate');
  assert.equal(h.run('prefs.motion'), 'extra');
  assert.equal(h.run('document.documentElement.dataset.motion'), 'extra');
  const payload = JSON.parse(h.run('JSON.stringify(preferencesPayload())'));
  assert.equal(payload.theme_pack, 'light-frost');
  assert.equal(payload.theme, 'slate');
  assert.equal(payload.motion, 'extra');
});

test('a Customize accent chosen after a pack still wins', async () => {
  const h = harness();
  await h.login();
  h.handle(async (path, request) => {
    if (path !== '/api/preferences') return response(404, { detail: path });
    return response(200, JSON.parse(request.body));
  });
  h.elements.get('theme').value = 'dark-frost';
  await h.elements.get('theme').listeners.change();
  h.elements.get('pref-accent').value = 'gold';
  h.elements.get('pref-accent').listeners.change();
  assert.equal(h.run('document.documentElement.dataset.accent'), 'gold');
  assert.equal(h.run('prefs.accent'), 'gold');
  assert.equal(JSON.parse(h.run('JSON.stringify(preferencesPayload())')).accent, 'gold');
});

test('an account with no stored motion keeps an explicit Normal on the wire', async () => {
  const h = harness();
  await h.login();
  const payload = JSON.parse(h.run('JSON.stringify(preferencesPayload())'));
  assert.equal(payload.motion, 'normal');
  const seeded = h.requests.filter(item => item.path === '/api/preferences' && item.request && item.request.method === 'PUT');
  assert.ok(seeded.length >= 1, 'first sign-in writes the device motion level once');
  assert.equal(JSON.parse(seeded[0].request.body).motion, 'normal');
});
