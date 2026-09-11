// The hybrid-frost theme lives entirely in two token maps in styles.css. These
// tests keep it that way: both themes define the same tokens, components never
// hard-code colors, every frosted panel has a solid fallback, the accent stays
// apart from the category palette, and text stays readable with no blur at all.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const appJs = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

function block(selector) {
  const start = css.indexOf(`${selector} {`);
  assert.ok(start !== -1, `styles.css has no ${selector} block`);
  return css.slice(css.indexOf('{', start) + 1, css.indexOf('}', start));
}

function tokens(selector) {
  const map = new Map();
  for (const match of block(selector).matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) map.set(match[1], match[2].trim());
  return map;
}

const themes = { dark: tokens(':root'), light: tokens(':root[data-theme="slate"]') };
const outsideMaps = css
  .replace(block(':root'), '')
  .replace(block(':root[data-theme="slate"]'), '');

function rgba(value) {
  const hex = /^#([0-9a-f]{6})$/i.exec(value);
  if (hex) return [0, 2, 4].map(i => parseInt(hex[1].slice(i, i + 2), 16) / 255).concat(1);
  const fn = /^rgba?\(([^)]+)\)$/.exec(value);
  assert.ok(fn, `not a color: ${value}`);
  const parts = fn[1].split(',').map(part => Number(part.trim()));
  return [parts[0] / 255, parts[1] / 255, parts[2] / 255, parts.length > 3 ? parts[3] : 1];
}

const over = (top, bottom) => top.slice(0, 3).map((c, i) => c * top[3] + bottom[i] * (1 - top[3])).concat(1);
const channel = c => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const luminance = ([r, g, b]) => 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

function lab([r, g, b]) {
  const [x, y, z] = [
    (channel(r) * 0.4124 + channel(g) * 0.3576 + channel(b) * 0.1805) / 0.95047,
    channel(r) * 0.2126 + channel(g) * 0.7152 + channel(b) * 0.0722,
    (channel(r) * 0.0193 + channel(g) * 0.1192 + channel(b) * 0.9505) / 1.08883,
  ].map(t => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116));
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
}
const distance = (a, b) => Math.hypot(...lab(a).map((value, i) => value - lab(b)[i]));

test('light and dark define exactly the same tokens', () => {
  assert.deepEqual([...themes.light.keys()].sort(), [...themes.dark.keys()].sort());
  for (const name of ['--bg', '--bg-accent', '--surface', '--surface-elevated', '--frost', '--frost-strong',
    '--hairline', '--accent', '--accent-ink', '--accent-soft', '--radius', '--space-2', '--text', '--muted',
    '--icon-primary', '--icon-secondary']) {
    assert.ok(themes.light.has(name), `${name} is missing from the theme maps`);
  }
});

test('every var() in styles.css is a theme token, and the legacy names are gone', () => {
  const setByScript = new Set(['--chip-color']);
  const used = new Set(Array.from(css.matchAll(/var\((--[a-z0-9-]+)/g), match => match[1]));
  const undefinedTokens = [...used].filter(name => !themes.dark.has(name) && !setByScript.has(name)).sort();
  assert.deepEqual(undefinedTokens, []);
  for (const legacy of ['--lime', '--dark', '--panel', '--ink', '--line']) {
    assert.ok(!new RegExp(`${legacy}\\b(?!-)`).test(css), `${legacy} is still used`);
  }
});

test('components read colors from tokens, never raw hex or rgb values', () => {
  const raw = Array.from(outsideMaps.matchAll(/#[0-9a-f]{3,8}\b|rgba?\(/gi), match => match[0]);
  assert.deepEqual(raw, []);
});

test('every frosted panel turns solid when blur is unavailable or unwanted', () => {
  const frosted = /\n([^{}@]+)\{\s*-webkit-backdrop-filter: blur\(var\(--frost\)\)/.exec(css);
  assert.ok(frosted, 'no frosted chrome rule');
  const selectors = frosted[1].split(',').map(item => item.trim()).filter(Boolean);
  const reduced = /@media \(prefers-reduced-transparency: reduce\)[^{]*\{([\s\S]*?)\n\}/.exec(css);
  assert.ok(reduced, 'no reduced-transparency media query');
  assert.match(reduced[1], /--surface: var\(--surface-solid\)/);
  const cleared = /\n\s*([^{}]+)\{\s*-webkit-backdrop-filter: none;\s*backdrop-filter: none;/.exec(reduced[1]);
  assert.ok(cleared, 'reduced-transparency mode does not remove backdrop filters');
  const clearedSelectors = new Set(cleared[1].split(',').map(item => item.trim()));
  assert.deepEqual(selectors.filter(selector => !clearedSelectors.has(selector)), []);
  assert.match(css, /@supports not \(\(backdrop-filter: blur\(1px\)\) or \(-webkit-backdrop-filter: blur\(1px\)\)\)/);
});

test('the accent is clearly different from every category color in both themes', () => {
  const categories = Array.from(appJs.matchAll(/id: "([a-z]+)", label: "[^"]+", color: "(#[0-9a-f]{6})"/g));
  assert.equal(categories.length, 8);
  for (const [theme, map] of Object.entries(themes)) {
    const accent = rgba(map.get('--accent'));
    for (const [, id, color] of categories) {
      assert.ok(distance(accent, rgba(color)) >= 15, `${theme} accent is too close to the ${id} category`);
    }
  }
});

test('text stays readable with frost composited straight over the page, no blur', () => {
  const AA = 4.5;
  for (const [theme, map] of Object.entries(themes)) {
    const color = name => rgba(map.get(name));
    const pages = [color('--bg'), color('--bg-accent')];
    for (const page of pages) {
      for (const surface of ['--surface', '--surface-elevated', '--surface-card']) {
        const backdrop = over(color(surface), page);
        for (const ink of ['--text', '--muted', '--accent', '--error']) {
          assert.ok(contrast(color(ink), backdrop) >= AA, `${theme}: ${ink} on ${surface} is below AA`);
        }
      }
    }
    for (const [ink, fill] of [['--text', '--surface-solid'], ['--text', '--field'], ['--muted', '--grid-cell'],
      ['--accent-ink', '--accent'], ['--block-locked-ink', '--block-locked'], ['--block-flex-ink', '--block-flex'],
      ['--badge-ink', '--ok'], ['--badge-ink', '--warn'], ['--badge-ink', '--risk'], ['--danger-ink', '--danger-bg']]) {
      assert.ok(contrast(color(ink), color(fill)) >= AA, `${theme}: ${ink} on ${fill} is below AA`);
    }
  }
});

test('the page resolves the theme in <head> and menus offer System, Light and Dark', () => {
  assert.match(html, /<html lang="en" data-theme="slate">/);
  assert.ok(html.indexOf('<script src="/static/theme.js"></script>') < html.indexOf('</head>'),
    'theme.js must run before the body paints');
  for (const id of ['theme', 'pref-theme']) {
    const select = new RegExp(`<select id="${id}">(.*?)</select>`).exec(html);
    assert.ok(select, `no #${id} select`);
    assert.deepEqual(Array.from(select[1].matchAll(/<option value="([a-z]+)">([^<]+)<\/option>/g), m => [m[1], m[2]]),
      [['system', 'System'], ['slate', 'Light'], ['nocturne', 'Dark']]);
  }
});

test('every icon used in the page exists in the sprite and is hidden from screen readers', () => {
  const symbols = new Set(Array.from(html.matchAll(/<symbol id="(i-[a-z-]+)"/g), match => match[1]));
  const uses = Array.from(html.matchAll(/<svg class="icon" aria-hidden="true"><use href="#(i-[a-z-]+)"\/><\/svg>/g),
    match => match[1]);
  assert.ok(uses.length >= 10);
  assert.deepEqual(uses.filter(name => !symbols.has(name)), []);
  assert.equal((html.match(/<use href=/g) || []).length, uses.length, 'an icon is missing aria-hidden');
});
