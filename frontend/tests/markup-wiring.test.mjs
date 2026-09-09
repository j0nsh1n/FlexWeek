// app.js runs against the real document, so an element it looks up at load must
// already exist when the script executes. The DOM-stub tests cannot catch this:
// they build every element up front, so a control declared after the script tag
// still resolves for them and silently resolves to null in a real browser.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const source = readFileSync(new URL('../app.js', import.meta.url), 'utf8');

const scriptTag = html.match(/<script\b[^>]*src="[^"]*app\.js"[^>]*>/);
assert.ok(scriptTag, 'index.html must load app.js');
const scriptIsDeferred = /\bdefer\b/.test(scriptTag[0]) || /\btype="module"\b/.test(scriptTag[0]);

/** Ids declared after app.js is loaded, which do not exist while it runs. */
function idsDeclaredAfterTheScript() {
  const after = html.slice(html.indexOf(scriptTag[0]) + scriptTag[0].length);
  return new Set(Array.from(after.matchAll(/\bid="([^"]+)"/g), match => match[1]));
}

/** Ids app.js resolves at module load, outside any function body. */
function idsLookedUpAtLoad() {
  const found = new Set();
  let depth = 0;
  for (const line of source.split('\n')) {
    const atTopLevel = depth === 0;
    if (atTopLevel) {
      for (const match of line.matchAll(/getElementById\(["']([^"']+)["']\)/g)) found.add(match[1]);
    }
    for (const char of line) {
      if (char === '{') depth += 1;
      else if (char === '}') depth = Math.max(0, depth - 1);
    }
  }
  return found;
}

test('every element app.js looks up at load exists by the time it runs', () => {
  if (scriptIsDeferred) return; // deferred execution happens after parsing, so all ids exist
  const late = idsDeclaredAfterTheScript();
  const dead = Array.from(idsLookedUpAtLoad()).filter(id => late.has(id)).sort();
  assert.deepEqual(dead, [], `app.js resolves these to null in a real browser: ${dead.join(', ')}`);
});

test('app.js is deferred, so markup may be declared in any order', () => {
  assert.ok(
    scriptIsDeferred,
    'app.js must be deferred or a module; without it, any control declared below the script tag is dead',
  );
});
