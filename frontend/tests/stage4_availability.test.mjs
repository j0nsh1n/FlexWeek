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
const NOW = new Date(2026, 8, 14, 12, 0, 0);

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
    const attributes = new Map();
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
      setAttribute(name, value = '') { attributes.set(name, value); if (name === 'open') this.open = true; },
      removeAttribute(name) { attributes.delete(name); if (name === 'open') this.open = false; },
      getAttribute(name) { return attributes.get(name) ?? null; },
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
    elements, requests, run: code => vm.runInContext(code, context),
    handle: fn => { handler = fn; },
    async login(preferences = { theme: 'nocturne' }) {
      await tick();
      handler = async path => {
        if (path.startsWith('/api/assignments')) return response(200, { assignments: [] });
        if (path.startsWith('/api/weeks')) return response(200, { weeks: [] });
        if (path.startsWith('/api/week')) return response(200, { week_start: weekOf(path), blocks: [], revision: 0 });
        return response(200, preferences);
      };
      await vm.runInContext("loadAccount({id:1,username:'student1'})", context);
    },
  };
}

const availability = {
  protected: [{ kind: 'meal', days: [0, 2], start: '18:00', duration_min: 60 }],
  study_windows: [{ days: [1, 3], start: '16:00', duration_min: 120 }],
  day_cutoff: '21:00',
};

async function submitPreferences(h) {
  await h.elements.get('prefs-form').listeners.submit({
    submitter: { value: 'save' }, preventDefault() {},
  });
}

test('availability preferences load and save without losing any window', async () => {
  const h = harness();
  await h.login({ theme: 'nocturne', ...availability });
  assert.deepEqual(JSON.parse(h.run('JSON.stringify(readAvailabilityEdit().value)')), availability);

  let saved;
  h.handle(async (path, options) => {
    if (path === '/api/preferences' && options.method === 'PUT') {
      saved = JSON.parse(options.body);
      return response(200, saved);
    }
    throw new Error(`Unexpected request ${path}`);
  });
  await submitPreferences(h);
  assert.deepEqual({
    protected: saved.protected,
    study_windows: saved.study_windows,
    day_cutoff: saved.day_cutoff,
  }, availability);
});

test('overlapping protected time is rejected before a request is sent', async () => {
  const h = harness();
  await h.login();
  h.run(`beginAvailabilityEdit({protected: [
    {kind:'meal',days:[0],start:'17:00',duration_min:60},
    {kind:'commute',days:[0,1],start:'17:30',duration_min:60}
  ], study_windows: [], day_cutoff: null})`);
  const before = h.requests.length;
  await submitPreferences(h);
  assert.equal(h.requests.length, before);
  assert.match(h.elements.get('prefs-error').textContent, /overlap/i);
});

test('adjacent protected time and the same clock time on another day save successfully', async () => {
  const h = harness();
  await h.login();
  h.run(`beginAvailabilityEdit({protected: [
    {kind:'meal',days:[0],start:'17:00',duration_min:60},
    {kind:'commute',days:[0],start:'18:00',duration_min:60},
    {kind:'downtime',days:[1],start:'17:30',duration_min:60}
  ], study_windows: [], day_cutoff: null})`);
  let put = null;
  h.handle(async (path, options) => {
    if (path === '/api/preferences' && options.method === 'PUT') {
      put = JSON.parse(options.body);
      return response(200, put);
    }
    throw new Error(`Unexpected request ${path}`);
  });
  await submitPreferences(h);
  assert.equal(put.protected.length, 3);
  assert.equal(h.elements.get('prefs-error').hidden, true);
});

test('availability totals count the union of protected time and cutoff', () => {
  const h = harness();
  const effect = JSON.parse(h.run(`JSON.stringify(availabilityEffect({
    protected: [
      {kind:'downtime',days:[0],start:'18:00',duration_min:120},
      {kind:'meal',days:[0],start:'21:30',duration_min:60}
    ],
    study_windows: [], day_cutoff: '21:00'
  }))`));
  // Seven 21:00–23:00 cutoffs are 840 minutes; Monday 18:00–20:00 adds 120.
  assert.deepEqual(effect, { protected_min: 960, remaining_min: 6180, study_count: 0 });
});

test('calendar paints hard and preferred hours on the intended weekdays', () => {
  const h = harness();
  const overlays = JSON.parse(h.run(`JSON.stringify((() => {
    prefs = {protected:[{kind:'meal',days:[0],start:'18:00',duration_min:60}],
      study_windows:[{days:[1],start:'16:00',duration_min:120}],day_cutoff:null};
    const lanes = Array.from({length:7}, () => document.createElement('div'));
    renderAvailabilityOverlays(lanes);
    return lanes.map(lane => lane.children.map(item => ({
      className:item.className, top:item.style.top, height:item.style.height,
      hidden:item.getAttribute('aria-hidden')
    })));
  })())`));
  assert.deepEqual(overlays[0], [{ className: 'availability-overlay protected-time', top: '33rem', height: '2.75rem', hidden: 'true' }]);
  assert.deepEqual(overlays[1], [{ className: 'availability-overlay study-time', top: '27.5rem', height: '5.5rem', hidden: 'true' }]);
  assert.ok(overlays.slice(2).every(day => day.length === 0));
});

test('the settings controls and availability script are present in the page', () => {
  assert.match(html, /id="availability-settings"/);
  assert.match(html, /id="protected-add"/);
  assert.match(html, /id="study-add"/);
  assert.match(html, /id="availability-cutoff"/);
  assert.match(html, /src="\/static\/availability\.js"\s+defer/);
});
