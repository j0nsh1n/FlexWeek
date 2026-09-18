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

const THEME_SELECTORS = {
  dark: ':root',
  light: ':root[data-theme="slate"]',
  'dark-frost': ':root[data-theme="dark-frost"]',
  'light-frost': ':root[data-theme="light-frost"]',
  // A preset palette is audited exactly like a pack: same tokens, AA text, accent distance.
  terminal: ':root[data-preset="terminal"]',
  poster: ':root[data-preset="poster"]',
  'high-contrast': ':root[data-preset="high-contrast"]',
  ink: ':root[data-preset="ink"]',
  'ink-light': ':root[data-theme="slate"][data-preset="ink"]',
  'ink-light-frost': ':root[data-theme="light-frost"][data-preset="ink"]',
};
const ACCENT_NAMES = ['sky', 'gold', 'sea', 'sand'];
const themes = Object.fromEntries(Object.entries(THEME_SELECTORS).map(([name, selector]) => [name, tokens(selector)]));
const accentMaps = [
  ...ACCENT_NAMES.map(name => `:root[data-accent="${name}"]`),
  ...ACCENT_NAMES.flatMap(name => [
    `:root[data-theme="slate"][data-accent="${name}"]`,
    `:root[data-theme="light-frost"][data-accent="${name}"]`,
  ]),
];
let outsideMaps = css;
for (const selector of [...Object.values(THEME_SELECTORS), ...accentMaps]) {
  outsideMaps = outsideMaps.replace(block(selector), '');
}

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

test('light, dark and both frost packs define exactly the same tokens', () => {
  const names = [...themes.dark.keys()].sort();
  for (const [theme, map] of Object.entries(themes)) {
    assert.deepEqual([...map.keys()].sort(), names, `${theme} token names differ`);
  }
  for (const name of ['--bg', '--bg-accent', '--surface', '--surface-elevated', '--frost', '--frost-strong',
    '--hairline', '--accent', '--accent-ink', '--accent-soft', '--radius', '--space-2', '--text', '--muted',
    '--icon-primary', '--icon-secondary']) {
    assert.ok(themes.light.has(name), `${name} is missing from the theme maps`);
  }
});

test('every var() in styles.css is a theme token, and the legacy names are gone', () => {
  const setByScript = new Set(['--chip-color', '--block-color']);
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

test('a page the desktop app reopened after it stopped gets the same solid panels', () => {
  const frosted = /\n([^{}@]+)\{\s*-webkit-backdrop-filter: blur\(var\(--frost\)\)/.exec(css)[1]
    .split(',').map(item => item.trim()).filter(Boolean);
  assert.match(css, /:root\[data-frost="off"\][^{]*\{[^}]*--surface: var\(--surface-solid\)/);
  for (const theme of ['slate', 'light-frost', 'dark-frost']) {
    assert.match(css, new RegExp(`:root\\[data-frost="off"\\]\\[data-theme="${theme}"\\]`));
  }
  const cleared = /:root\[data-frost="off"\] :is\(([^)]*)\), :root\[data-frost="off"\] \.prefs-dialog::backdrop \{\s*-webkit-backdrop-filter: none;\s*backdrop-filter: none;/.exec(css);
  assert.ok(cleared, 'recovery mode does not remove backdrop filters');
  assert.deepEqual(cleared[1].split(',').map(item => item.trim()).sort(), [...frosted].sort());
});

test('every accent on offer stays clearly apart from every category colour', () => {
  const categories = Array.from(appJs.matchAll(/id: "([a-z]+)", label: "[^"]+", color: "(#[0-9a-f]{6})"/g));
  assert.equal(categories.length, 8);
  const accents = [];
  for (const [theme, map] of Object.entries(themes)) {
    accents.push([`${theme} default`, map.get('--accent')]);
  }
  for (const name of ACCENT_NAMES) {
    accents.push([`dark ${name}`, tokens(`:root[data-accent="${name}"]`).get('--accent')]);
    accents.push([`light ${name}`, tokens(`:root[data-theme="slate"][data-accent="${name}"]`).get('--accent')]);
  }
  for (const [label, hex] of accents) {
    const accent = rgba(hex);
    for (const [, id, color] of categories) {
      assert.ok(distance(accent, rgba(color)) >= 15, `${label} is too close to the ${id} category`);
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

test('the page resolves the look in <head> and Look offers packs then presets', () => {
  assert.match(html, /<html lang="en" data-theme="slate">/);
  assert.ok(html.indexOf('<script src="/static/theme.js"></script>') < html.indexOf('</head>'),
    'theme.js must run before the body paints');
  const packs = [['system', 'System'], ['light-frost', 'Light frost'], ['dark-frost', 'Dark frost'],
    ['nocturne', 'Nocturne'], ['slate', 'Slate']];
  const looks = packs.concat([['terminal', 'Terminal'], ['poster', 'Poster'], ['ink', 'Ink'],
    ['high-contrast', 'High contrast']]);
  for (const id of ['theme', 'pref-theme']) {
    const select = new RegExp(`<select id="${id}">(.*?)</select>`).exec(html);
    assert.ok(select, `no #${id} select`);
    assert.deepEqual(Array.from(select[1].matchAll(/<option value="([a-z-]+)">([^<]+)<\/option>/g), m => [m[1], m[2]]),
      looks);
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

// Motion, added in 0.11. The rules below are what keeps it from becoming the
// flicker the Windows build already suffers from: nothing frosted moves, and
// nothing moves at all for a system that asked for less motion.
const FROSTED = ['.top', '.week-nav', '.side', '.auth-panel', '.save-actions', '.empty-week',
  '.prefs-dialog', '.context-menu', '.reminder-toast'];

function balancedBlock(source, opening) {
  const start = source.indexOf(opening);
  assert.ok(start !== -1, `styles.css has no ${opening}`);
  let depth = 0;
  for (let i = source.indexOf('{', start); i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    else if (source[i] === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(source.indexOf('{', start) + 1, i);
    }
  }
  assert.fail(`${opening} is not balanced`);
}

const motionBlock = balancedBlock(css, '@media (prefers-reduced-motion: no-preference)');

test('no rule animates or transitions backdrop-filter, and none uses the all shorthand', () => {
  for (const match of css.matchAll(/(?:transition|animation)(?:-property)?\s*:\s*([^;}]+)/g)) {
    assert.doesNotMatch(match[1], /backdrop-filter/, `${match[1].trim()} animates the frosted layer`);
    assert.doesNotMatch(match[1], /\ball\b/, `${match[1].trim()} would sweep up backdrop-filter`);
  }
});

test('keyframes move opacity and transform only', () => {
  const names = [...css.matchAll(/@keyframes\s+([\w-]+)/g)].map(match => match[1]);
  assert.deepEqual(names, ['view-fade-in', 'view-rise-in', 'block-pop-in', 'block-draw-on']);
  for (const name of names) {
    const body = balancedBlock(css, `@keyframes ${name}`);
    for (const declaration of body.matchAll(/([a-z-]+)\s*:/g)) {
      assert.ok(['opacity', 'transform'].includes(declaration[1]),
        `@keyframes ${name} may not move ${declaration[1]}`);
    }
  }
});

test('every animation sits behind the system reduced-motion setting', () => {
  const outsideTheGate = css.replace(motionBlock, '');
  assert.doesNotMatch(outsideTheGate, /\banimation\s*:/,
    'an animation outside prefers-reduced-motion: no-preference ignores the system setting');
});

test('Motion set to Off animates nothing', () => {
  const rules = motionBlock.split('}').map(rule => rule.split('{')[0].trim()).filter(Boolean);
  for (const rule of rules) {
    assert.ok(rule.includes(':not([data-motion="off"])') || rule.includes('[data-motion="extra"]'),
      `${rule} still animates when Motion is Off`);
  }
});

test('nothing frosted is animated', () => {
  for (const selector of FROSTED) {
    assert.ok(!motionBlock.includes(selector),
      `${selector} has backdrop-filter, so animating it risks the Windows flicker`);
  }
});

test('the accepted late block draws on at Normal, not only at Extra', () => {
  assert.match(motionBlock, /:not\(\[data-motion="off"\]\)[^{]*\.block\.is-drawn-on[^}]*animation:\s*block-draw-on/);
});

test('Extra is the level that adds the pop-in, and Normal only fades', () => {
  assert.match(motionBlock, /\[data-motion="extra"\][^{]*\.block\.is-new/);
  assert.match(motionBlock, /:not\(\[data-motion="off"\]\)[^{]*#week[\s\S]*?animation:\s*view-fade-in/);
});

// Look knobs, added after 0.11.0. Each attribute on <html> may move one kind of
// thing only, so a preset cannot smuggle a colour or an animation in through a
// knob, and Customize stays a set of independent switches.
function knobRules(knob) {
  const rules = [];
  const pattern = new RegExp(`\n(:root\\[data-${knob}="([a-z]+)"\\][^{]*)\\{([^}]*)\\}`, 'g');
  for (const match of css.matchAll(pattern)) rules.push({ selector: match[1].trim(), value: match[2], body: match[3] });
  assert.ok(rules.length > 0, `styles.css has no data-${knob} rule`);
  return rules;
}
const properties = body => Array.from(body.matchAll(/(?:^|;|\s)([a-z-]+|--[a-z0-9-]+)\s*:/g), match => match[1]);

test('each look knob moves only the properties it names', () => {
  const allowed = {
    corners: name => name.startsWith('--radius'),
    depth: name => name.startsWith('--shadow'),
    font: name => name === 'font-family',
    text: name => name === 'font-size',
    density: name => name === '--hour-h' || name.startsWith('--space-'),
    surface: name => name.startsWith('--surface') || name.endsWith('backdrop-filter'),
    blocks: name => ['background', 'color', 'border-color', 'border-left-width'].includes(name),
  };
  for (const [knob, ok] of Object.entries(allowed)) {
    for (const rule of knobRules(knob)) {
      for (const name of properties(rule.body)) {
        assert.ok(ok(name), `${rule.selector} moves ${name}, which is not this knob's job`);
      }
    }
  }
});

test('the flat surface turns solid and clears blur on exactly the frosted panels', () => {
  const frosted = /\n([^{}@]+)\{\s*-webkit-backdrop-filter: blur\(var\(--frost\)\)/.exec(css)[1]
    .split(',').map(item => item.trim()).filter(Boolean);
  assert.match(css, /:root\[data-surface="flat"\]\s*\{[^}]*--surface: var\(--surface-solid\)/);
  const cleared = /:root\[data-surface="flat"\] :is\(([^)]*)\), :root\[data-surface="flat"\] \.prefs-dialog::backdrop \{\s*-webkit-backdrop-filter: none;\s*backdrop-filter: none;/.exec(css);
  assert.ok(cleared, 'the flat surface does not remove backdrop filters');
  assert.deepEqual(cleared[1].split(',').map(item => item.trim()).sort(), [...frosted].sort());
});

test('a block takes its category colour from --block-color, so a look can decide where it lands', () => {
  assert.match(appJs, /el\.style\.setProperty\("--block-color", color\)/);
  assert.match(css, /\.block \{[^}]*border-left: 3px solid var\(--block-color, var\(--block-edge\)\)/);
  assert.match(css, /\.flex-block \{[^}]*border-left-color: var\(--block-color, var\(--flex\)\)/);
  assert.match(css, /:root\[data-blocks="outlined"\] \.block \{[^}]*background: transparent/);
});

test('pill corners cannot turn a calendar block into a capsule that clips its title', () => {
  // Seen in a real grab: 999px on a tall School block rounded the text away.
  assert.match(css, /\.block \{[^}]*border-radius: min\(var\(--radius-sm\), 0\.5rem\)/);
  const pill = /:root\[data-corners="pill"\] \{([^}]*)\}/.exec(css);
  assert.ok(pill && /--radius-sm: 999px/.test(pill[1]), 'chips still get true pill corners');
});

test('the Terminal preset changes every knob the frost packs leave at default', () => {
  const lookJs = readFileSync(new URL('../look.js', import.meta.url), 'utf8');
  const preset = /terminal: \{([\s\S]*?)\}/.exec(lookJs);
  assert.ok(preset, 'look.js has no terminal preset');
  const values = Object.fromEntries(Array.from(preset[1].matchAll(/(\w+): "([a-z]+)"/g), m => [m[1], m[2]]));
  assert.deepEqual(values, {
    surface: 'flat', corners: 'sharp', depth: 'flat', font: 'mono',
    blocks: 'outlined', density: 'compact', text: 'normal',
  });
  assert.ok(html.indexOf('<script src="/static/look.js"></script>') < html.indexOf('</head>'),
    'look.js must run before the body paints');
});

test('Poster, Ink and High contrast each name a full knob bundle', () => {
  const lookJs = readFileSync(new URL('../look.js', import.meta.url), 'utf8');
  const named = (name) => {
    const match = new RegExp(`${name}: \\{([\\s\\S]*?)\\}`).exec(lookJs);
    assert.ok(match, `look.js has no ${name} preset`);
    return Object.fromEntries(Array.from(match[1].matchAll(/(\w+): "([a-z]+)"/g), m => [m[1], m[2]]));
  };
  assert.deepEqual(named('poster'), {
    surface: 'flat', corners: 'sharp', depth: 'hard', font: 'sans',
    blocks: 'filled', density: 'compact', text: 'large',
  });
  assert.deepEqual(named('ink'), {
    surface: 'flat', corners: 'sharp', depth: 'flat', font: 'serif',
    blocks: 'edge', density: 'comfortable', text: 'normal',
  });
  assert.deepEqual(named('"high-contrast"'), {
    surface: 'flat', corners: 'sharp', depth: 'hard', font: 'sans',
    blocks: 'outlined', density: 'comfortable', text: 'large',
  });
  const select = /<select id="pref-theme">(.*?)<\/select>/.exec(html);
  assert.ok(select, 'no #pref-theme select');
  assert.ok(select[1].includes('value="terminal"'), 'Terminal belongs in Look');
  assert.ok(select[1].includes('value="high-contrast"'), 'High contrast belongs in Look');
  assert.doesNotMatch(html, /id="pref-preset"/);
});

test('large text makes the More menu readable', () => {
  assert.match(css, /html\[data-text="large"\] \.week-menu > summary/);
  assert.match(css, /html\[data-text="large"\] \.week-menu-items \{\s*min-width: 18rem/);
});
