// Look choice. A pack is System, Light frost, Dark frost, Nocturne or Slate.
// System follows the device light or dark setting and switches when it changes;
// the other four stay put. The stylesheet reads the resolved name on
// <html data-theme>, which is slate, nocturne, light-frost or dark-frost.
// This script runs in <head>, before the body exists, so the first paint already
// matches the device. Signed-out screens are always System.
const systemDark = typeof matchMedia === "function" ? matchMedia("(prefers-color-scheme: dark)") : null;
const PACKS = ["system", "light-frost", "dark-frost", "nocturne", "slate"];
const ACCENTS = ["default", "sky", "gold", "sea", "sand"];
let packChoice = "system";
// The desktop app reopens the page with ?recovered=1 after its page process stopped.
// That session swaps the frosted glass for the solid panels, which ask far less of
// the graphics driver, from the first paint on. auth.js finishes the recovery.
const pageRecovered = typeof location !== "undefined" && /(?:^\?|&)recovered=1(?:&|$)/.test(location.search);
if (pageRecovered) document.documentElement.dataset.frost = "off";

function knownPack(pack) {
  return PACKS.indexOf(pack) === -1 ? "system" : pack;
}

function packAxis(pack) {
  const chosen = knownPack(pack);
  if (chosen === "light-frost" || chosen === "slate") return "slate";
  if (chosen === "dark-frost" || chosen === "nocturne") return "nocturne";
  return "system";
}

function packMotion(pack) {
  const chosen = knownPack(pack);
  return chosen === "light-frost" || chosen === "dark-frost" ? "extra" : "normal";
}

function resolvedPackTheme(pack) {
  const chosen = knownPack(pack);
  if (chosen === "system") return systemDark && systemDark.matches ? "nocturne" : "slate";
  return chosen;
}

function applyPack(pack) {
  packChoice = knownPack(pack);
  document.documentElement.dataset.pack = packChoice;
  document.documentElement.dataset.theme = resolvedPackTheme(packChoice);
  return packChoice;
}

function applyTheme(choice) {
  return applyPack(choice);
}

function applyAccent(name) {
  const chosen = ACCENTS.indexOf(name) === -1 ? "default" : name;
  if (chosen === "default") delete document.documentElement.dataset.accent;
  else document.documentElement.dataset.accent = chosen;
  return chosen;
}

function applyAccentChips(on) {
  document.documentElement.dataset.accentChips = on ? "on" : "off";
  return Boolean(on);
}

if (systemDark && typeof systemDark.addEventListener === "function") {
  systemDark.addEventListener("change", function () {
    if (packChoice === "system") applyPack("system");
  });
}

applyPack("system");
