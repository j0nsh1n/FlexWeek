// The frontend scripts run against the real document, so an element one looks up
// at load must already exist when it executes. The DOM-stub tests cannot catch
// this: they build every element up front, so a control declared after a script
// tag still resolves for them and silently resolves to null in a real browser.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { appScripts, scriptTags } from './app-scripts.mjs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

const isDeferred = tag => /\bdefer\b/.test(tag) || /\btype="module"\b/.test(tag);

/** Ids declared after the first script tag, which may not exist while scripts run. */
function idsDeclaredAfterTheScripts() {
  const after = html.slice(html.indexOf(scriptTags[0][0]));
  return new Set(Array.from(after.matchAll(/\bid="([^"]+)"/g), match => match[1]));
}

/** Ids a script resolves at load, outside any function body. */
function idsLookedUpAtLoad(source) {
  const found = new Set();
  let depth = 0;
  for (const line of source.split('\n')) {
    if (depth === 0) {
      for (const match of line.matchAll(/getElementById\(["']([^"']+)["']\)/g)) found.add(match[1]);
    }
    for (const char of line) {
      if (char === '{') depth += 1;
      else if (char === '}') depth = Math.max(0, depth - 1);
    }
  }
  return found;
}

test('index.html loads app.js and every script it loads exists', () => {
  assert.ok(appScripts.some(script => script.name === 'app.js'), 'index.html must load app.js');
  assert.ok(appScripts.every(script => script.code.length > 0));
});

test('every element a script looks up at load exists by the time it runs', () => {
  if (scriptTags.every(match => isDeferred(match[0]))) return; // deferred scripts run after parsing
  const late = idsDeclaredAfterTheScripts();
  const dead = appScripts.flatMap(script => Array.from(idsLookedUpAtLoad(script.code)))
    .filter(id => late.has(id)).sort();
  assert.deepEqual(dead, [], `these resolve to null in a real browser: ${dead.join(', ')}`);
});

test('every frontend script is deferred, so markup may be declared in any order', () => {
  for (const match of scriptTags) {
    assert.ok(isDeferred(match[0]), `${match[1]} must be deferred; without it, controls declared below it are dead`);
  }
});
