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
    localStorage: { getItem() { return null; }, removeItem() {} },
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


const CODES = [
  '0001-0001-0001-0001', '0002-0002-0002-0002', '0003-0003-0003-0003', '0004-0004-0004-0004',
  '0005-0005-0005-0005', '0006-0006-0006-0006', '0007-0007-0007-0007', '0008-0008-0008-0008',
];

function emptySnapshot(username = 'source_student') {
  return {
    format: 3, exported_at: '2026-09-15T12:00', username,
    weeks: [], assignments: [], preferences: { theme: 'system' }, routines: [],
  };
}

function accountLoad(path) {
  if (path.startsWith('/api/assignments')) return response(200, { assignments: [] });
  if (path === '/api/weeks') return response(200, { weeks: [] });
  if (path.startsWith('/api/week')) return response(200, { week_start: MONDAY, blocks: [], revision: 0 });
  if (path === '/api/preferences') return response(200, defaultPrefs);
  return null;
}

test('registration shows its one-time codes before first-week setup and does not retain them on the account', async () => {
  const h = harness();
  await tick();
  h.handle(async (path, request) => {
    if (path === '/api/auth/register') return response(201, { id: 4, username: 'new_student', recovery_codes: CODES });
    return accountLoad(path) || response(404, { detail: 'Unexpected request' });
  });
  h.elements.get('register-username').value = 'new_student';
  h.elements.get('register-password').value = 'a long enough password';
  await h.elements.get('register-form').listeners.submit({ preventDefault() {} });

  assert.equal(h.elements.get('recovery-codes-dialog').open, true);
  assert.deepEqual(h.elements.get('recovery-codes-list').children.map(item => item.children[0].textContent), CODES);
  assert.equal(h.run('Object.hasOwn(account, "recovery_codes")'), false);
  assert.equal(h.elements.get('setup-dialog').open, false);
  assert.equal(h.elements.get('recovery-codes-done').disabled, true);

  h.elements.get('recovery-codes-ack').checked = true;
  h.elements.get('recovery-codes-ack').listeners.change({ currentTarget: h.elements.get('recovery-codes-ack') });
  h.elements.get('recovery-codes-done').listeners.click();
  assert.equal(h.elements.get('recovery-codes-dialog').open, false);
  assert.equal(h.elements.get('recovery-codes-list').children.length, 0);
  assert.equal(h.elements.get('setup-dialog').open, true);
});

test('forgot password checks confirmation locally, then posts the code and opens the recovered account', async () => {
  const h = harness();
  await tick();
  h.elements.get('login-username').value = 'recover_me';
  h.elements.get('show-recover').listeners.click();
  assert.equal(h.elements.get('recover-screen').hidden, false);
  assert.equal(h.elements.get('recover-username').value, 'recover_me');

  h.elements.get('recover-code').value = 'A1B2C3D4E5F67890';
  h.elements.get('recover-password').value = 'replacement pass';
  h.elements.get('recover-password-confirm').value = 'different pass';
  const form = h.elements.get('recover-form');
  await form.listeners.submit({ preventDefault() {}, currentTarget: form });
  assert.equal(h.requests.filter(item => item.path === '/api/auth/recover').length, 0);
  assert.equal(h.elements.get('recover-error').textContent, 'The new passwords do not match.');

  h.elements.get('recover-password-confirm').value = 'replacement pass';
  let recoverBody = null;
  h.handle(async (path, request) => {
    if (path === '/api/auth/recover') {
      recoverBody = JSON.parse(request.body);
      return response(200, { id: 8, username: 'recover_me' });
    }
    return accountLoad(path) || response(404, { detail: 'Unexpected request' });
  });
  await form.listeners.submit({ preventDefault() {}, currentTarget: form });
  assert.deepEqual(recoverBody, {
    username: 'recover_me', code: 'A1B2C3D4E5F67890', password: 'replacement pass',
  });
  assert.equal(h.elements.get('planner').hidden, false);
  assert.equal(h.elements.get('account-name').textContent, 'recover_me');
  assert.equal(h.elements.get('status').textContent, 'Account recovered. Your other sessions were signed out.');
});

test('wrong confirmation passwords stay local and a wrong current password does not sign the account out', async () => {
  const h = harness();
  await h.login();
  const form = h.elements.get('change-password-form');
  h.elements.get('change-password-current').value = 'old password value';
  h.elements.get('change-password-new').value = 'new password value';
  h.elements.get('change-password-confirm').value = 'does not match';
  await form.listeners.submit({ preventDefault() {}, currentTarget: form });
  assert.equal(h.requests.filter(item => item.path === '/api/auth/password').length, 0);

  h.elements.get('change-password-confirm').value = 'new password value';
  h.handle(async path => path === '/api/auth/password'
    ? response(401, { detail: 'Incorrect password' })
    : response(404, { detail: 'Unexpected request' }));
  await form.listeners.submit({ preventDefault() {}, currentTarget: form });
  assert.equal(h.run('account.username'), 'comfort');
  assert.equal(h.elements.get('planner').hidden, false);
  assert.equal(h.elements.get('change-password-error').textContent, 'Incorrect password');
});

test('account location and recovery status name the signed-in account, origin and unused count', async () => {
  const h = harness();
  await h.login();
  h.handle(async path => {
    if (path === '/api/storage-info') return response(200, {
      mode: 'hosted', label: 'On your FlexWeek server', username: 'comfort', origin: 'https://school.example',
    });
    if (path === '/api/auth/recovery-status') return response(200, { remaining: 3 });
    return response(404, { detail: 'Unexpected request' });
  });
  await h.run('prepareStage6Account()');
  assert.equal(h.elements.get('account-location-label').textContent, 'On your FlexWeek server');
  assert.equal(h.elements.get('prefs-account').textContent, 'Signed in as comfort');
  assert.equal(h.elements.get('account-location-origin').textContent, 'https://school.example');
  assert.match(h.elements.get('account-sync-note').textContent, /same saved data/);
  assert.equal(h.elements.get('recovery-status').textContent, '3 unused recovery codes remain.');
});

test('account transfer files are distinct from week files and invalid references never reach preview', async () => {
  const h = harness();
  await h.login();
  const weekFile = JSON.stringify({ format: 'flexweek-week', version: 2, blocks: [], assignments: [] });
  h.elements.get('account-import-file').files = [{ text: async () => weekFile }];
  const before = h.requests.length;
  await h.elements.get('account-import-file').listeners.change();
  assert.equal(h.requests.length, before);
  assert.match(h.elements.get('transfer-error').textContent, /week export belongs under Import week/);

  const dangling = emptySnapshot();
  dangling.weeks.push({
    week_start: MONDAY, revision: 0,
    blocks: [{ id: 'session', kind: 'flexible', title: 'Essay', duration_min: 30, days: [0], assignment_id: 'missing' }],
  });
  h.elements.get('account-import-file').files = [{ text: async () => JSON.stringify(dangling) }];
  await h.elements.get('account-import-file').listeners.change();
  assert.equal(h.requests.length, before);
  assert.match(h.elements.get('transfer-error').textContent, /homework the account file does not include/);
});

test('preview shows removals, routines and settings before one acknowledged replacement', async () => {
  const h = harness();
  await h.login();
  const snapshot = emptySnapshot();
  const sent = [];
  h.handle(async (path, request) => {
    if (path === '/api/account-import/preview') {
      sent.push({ path, body: JSON.parse(request.body) });
      return response(200, { state_token: 'preview-token', source_username: 'source_student', changes: {
        weeks: { added: ['2026-09-07'], changed: [], removed: ['2026-08-31'] },
        assignments: { added: [], changed: ['essay'], removed: [] },
        routines: { added: [], changed: [], removed: ['school week'] }, preferences_changed: true,
      } });
    }
    if (path === '/api/account-import') {
      sent.push({ path, body: JSON.parse(request.body) });
      return response(200, { recovery_id: 'rp-1', weeks: [], assignments: [], preferences: {}, routines: [] });
    }
    return accountLoad(path) || response(404, { detail: 'Unexpected request' });
  });
  assert.equal(await h.run(`previewTransferSnapshot(${JSON.stringify(snapshot)})`), true);
  assert.equal(h.elements.get('account-import-source').textContent, 'From source_student. Review what will change in comfort.');
  assert.deepEqual(h.elements.get('account-import-diff').children.map(card => card.children[0].textContent), [
    'Weeks: 2 changes', 'Homework: 1 change', 'Routines: 1 change', 'Settings: will be replaced',
  ]);
  assert.deepEqual(h.elements.get('account-import-removals').children.map(item => item.textContent), [
    'Week: 2026-08-31', 'Routine: school week',
  ]);
  assert.equal(h.elements.get('account-import-confirm').disabled, true);
  h.elements.get('account-import-ack').checked = true;
  h.elements.get('account-import-ack').listeners.change({ currentTarget: h.elements.get('account-import-ack') });
  assert.equal(await h.run('applyTransfer()'), true);
  assert.equal(sent[1].body.state_token, 'preview-token');
  assert.deepEqual(sent[1].body.snapshot, snapshot);
  assert.match(sent[1].body.operation_id, /.+/);
  assert.equal(h.elements.get('status').textContent, 'Account data imported. The destination now matches the previewed file.');
});

test('a stale transfer cannot be confirmed again until the student chooses and reviews a fresh file', async () => {
  const h = harness();
  await h.login();
  const snapshot = emptySnapshot();
  h.handle(async path => path === '/api/account-import/preview'
    ? response(200, { state_token: 'old-token', source_username: 'source_student', changes: {
      weeks: { added: [], changed: [], removed: [] }, assignments: { added: [], changed: [], removed: [] },
      routines: { added: [], changed: [], removed: [] }, preferences_changed: false,
    } })
    : response(409, { detail: 'This preview is out of date. Refresh it before importing.' }));
  await h.run(`previewTransferSnapshot(${JSON.stringify(snapshot)})`);
  h.elements.get('account-import-ack').checked = true;
  assert.equal(await h.run('applyTransfer()'), false);
  assert.equal(h.elements.get('account-import-confirm').disabled, true);
  assert.equal(h.run('stage6Import.preview'), null);
  assert.match(h.elements.get('transfer-error').textContent, /review a fresh preview/);
});

test('account deletion requires the exact username and a wrong password leaves the session usable', async () => {
  const h = harness();
  await h.login();
  const form = h.elements.get('delete-account-form');
  h.elements.get('delete-account-username').value = 'wrong';
  h.elements.get('delete-account-password').value = 'a long enough password';
  await form.listeners.submit({ preventDefault() {}, currentTarget: form });
  assert.equal(h.requests.filter(item => item.path === '/api/auth/account').length, 0);
  assert.match(h.elements.get('delete-account-error').textContent, /Type comfort exactly/);

  h.elements.get('delete-account-username').value = 'comfort';
  h.handle(async path => path === '/api/auth/account'
    ? response(401, { detail: 'Incorrect password' })
    : response(404, { detail: 'Unexpected request' }));
  await form.listeners.submit({ preventDefault() {}, currentTarget: form });
  assert.equal(h.run('account.username'), 'comfort');
  assert.equal(h.elements.get('planner').hidden, false);
  assert.equal(h.elements.get('delete-account-error').textContent, 'Incorrect password');
});

test('replacing codes and changing the password keep secrets out of account state and update the current session', async () => {
  const h = harness();
  await h.login();
  const posts = [];
  h.handle(async (path, request) => {
    posts.push({ path, body: request.body ? JSON.parse(request.body) : null });
    if (path === '/api/auth/recovery-codes') return response(200, { recovery_codes: CODES, remaining: 8 });
    if (path === '/api/auth/password') return response(200, { id: 1, username: 'comfort' });
    return response(404, { detail: 'Unexpected request' });
  });

  const codesForm = h.elements.get('replace-codes-form');
  h.elements.get('replace-codes-password').value = 'current password';
  await codesForm.listeners.submit({ preventDefault() {}, currentTarget: codesForm });
  assert.equal(h.elements.get('recovery-codes-dialog').open, true);
  assert.equal(h.elements.get('recovery-status').textContent, '8 unused recovery codes remain.');
  assert.equal(h.run('Object.hasOwn(account, "recovery_codes")'), false);

  h.elements.get('recovery-codes-ack').checked = true;
  h.elements.get('recovery-codes-done').listeners.click();
  const passwordForm = h.elements.get('change-password-form');
  h.elements.get('change-password-current').value = 'current password';
  h.elements.get('change-password-new').value = 'new password value';
  h.elements.get('change-password-confirm').value = 'new password value';
  await passwordForm.listeners.submit({ preventDefault() {}, currentTarget: passwordForm });
  assert.deepEqual(posts, [
    { path: '/api/auth/recovery-codes', body: { password: 'current password' } },
    { path: '/api/auth/password', body: { current_password: 'current password', new_password: 'new password value' } },
  ]);
  assert.equal(h.run('account.username'), 'comfort');
  assert.equal(h.elements.get('status').textContent, 'Password changed. Other devices were signed out.');
});

test('a confirmed successful deletion clears the account and returns to Create account', async () => {
  const h = harness();
  await h.login();
  const form = h.elements.get('delete-account-form');
  h.elements.get('delete-account-username').value = 'comfort';
  h.elements.get('delete-account-password').value = 'a long enough password';
  h.handle(async path => path === '/api/auth/account'
    ? response(204)
    : response(404, { detail: 'Unexpected request' }));
  await form.listeners.submit({ preventDefault() {}, currentTarget: form });
  assert.equal(h.run('account'), null);
  assert.equal(h.elements.get('planner').hidden, true);
  assert.equal(h.elements.get('register-screen').hidden, false);
  assert.equal(h.elements.get('status').textContent, 'Account deleted. You can create a new account with that username.');
});

test('signing out erases an in-memory transfer snapshot and any displayed recovery codes', async () => {
  const h = harness();
  await h.login();
  h.run(`stage6Import={snapshot:${JSON.stringify(emptySnapshot())},preview:{state_token:'private'},accountId:1,operationId:'private-op'}`);
  h.run(`stage6RecoveryCodes=${JSON.stringify(CODES)}; renderRecoveryCodes()`);
  h.run('signedOut("Done", false)');
  assert.equal(h.run('stage6Import'), null);
  assert.equal(h.run('stage6RecoveryCodes.length'), 0);
  assert.equal(h.elements.get('recovery-codes-list').children.length, 0);
});
