// The frontend scripts run against the real document, so an element one looks up
// at load must already exist when it executes. The DOM-stub tests cannot catch
// this: they build every element up front, so a control declared after a script
// tag still resolves for them and silently resolves to null in a real browser.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { appScripts, scriptTags } from './app-scripts.mjs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const headEnd = html.indexOf('</head>');

const isDeferred = tag => /\bdefer\b/.test(tag) || /\btype="module"\b/.test(tag);
const codeOf = name => appScripts.find(script => script.name === name).code;

/** Ids declared after a script tag, which do not exist yet if that script runs immediately. */
function idsDeclaredAfter(tag) {
  const after = html.slice(tag.index + tag[0].length);
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
  for (const tag of scriptTags.filter(match => !isDeferred(match[0]))) {
    const late = idsDeclaredAfter(tag);
    const dead = Array.from(idsLookedUpAtLoad(codeOf(tag[1]))).filter(id => late.has(id)).sort();
    assert.deepEqual(dead, [], `${tag[1]} resolves these to null in a real browser: ${dead.join(', ')}`);
  }
});

test('scripts in <head> touch no page elements, and every script in <body> is deferred', () => {
  for (const tag of scriptTags) {
    if (tag.index < headEnd) {
      assert.doesNotMatch(codeOf(tag[1]), /getElementById|querySelector/,
        `${tag[1]} runs before the body exists, so it may only touch <html>`);
    } else {
      assert.ok(isDeferred(tag[0]), `${tag[1]} must be deferred; without it, controls declared below it are dead`);
    }
  }
});
