import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

export const scriptTags = Array.from(html.matchAll(/<script\b[^>]*\bsrc="\/static\/([^"]+\.js)"[^>]*>/g));

/** The frontend scripts, in the order index.html loads them. */
export const appScripts = scriptTags.map(match => ({
  name: match[1],
  code: readFileSync(new URL(`../${match[1]}`, import.meta.url), 'utf8'),
}));

/** Run each script separately, as a browser does, so a load-order mistake fails here too. */
export function runAppScripts(vm, context) {
  for (const script of appScripts) vm.runInContext(script.code, context, { filename: script.name });
}
