// Look knobs and presets, for this device only. A knob is one attribute on
// <html> that the stylesheet reads; a preset is a bundle of knob values plus a
// palette. Nothing here reaches /api/preferences: the fields are proposed in
// docs/stage8-appearance-contract.md and wait on owner approval. This runs in
// <head>, before the body exists, so the first paint already has the look and
// the script may only touch <html>.
const LOOK_KEY = "flexweek-look";
const LOOK_KNOBS = {
  surface: ["frost", "flat"],
  corners: ["round", "sharp", "pill"],
  depth: ["soft", "flat", "hard"],
  font: ["sans", "mono", "serif"],
  blocks: ["filled", "outlined", "edge"],
  density: ["comfortable", "compact"],
  text: ["small", "normal", "large"],
};
// The first value of each knob is what the packs already look like.
const LOOK_DEFAULTS = {
  surface: "frost", corners: "round", depth: "soft", font: "sans",
  blocks: "filled", density: "comfortable", text: "normal",
};
// A preset sets every knob and names a palette map in styles.css. "default" is
// the pack the account chose, untouched.
const LOOK_PRESETS = {
  default: {},
  terminal: {
    surface: "flat", corners: "sharp", depth: "flat", font: "mono",
    blocks: "outlined", density: "compact", text: "normal",
  },
  poster: {
    surface: "flat", corners: "sharp", depth: "hard", font: "sans",
    blocks: "filled", density: "compact", text: "large",
  },
  ink: {
    surface: "flat", corners: "sharp", depth: "flat", font: "serif",
    blocks: "edge", density: "comfortable", text: "normal",
  },
  "high-contrast": {
    surface: "flat", corners: "sharp", depth: "hard", font: "sans",
    blocks: "outlined", density: "comfortable", text: "large",
  },
  // The two soft looks. Every preset above is flat and sharp; these keep rounded corners and shadows.
  paper: {
    surface: "flat", corners: "round", depth: "soft", font: "serif",
    blocks: "filled", density: "comfortable", text: "normal",
  },
  pastel: {
    surface: "frost", corners: "pill", depth: "soft", font: "sans",
    blocks: "filled", density: "comfortable", text: "normal",
  },
};
let lookChoice = { preset: "default", knobs: {} };

function knownLookValue(knob, value) {
  const values = LOOK_KNOBS[knob];
  return values && values.indexOf(value) !== -1 ? value : null;
}

function sanitizeLook(raw) {
  const clean = { preset: "default", knobs: {} };
  if (!raw || typeof raw !== "object") return clean;
  if (Object.prototype.hasOwnProperty.call(LOOK_PRESETS, raw.preset)) clean.preset = raw.preset;
  const knobs = raw.knobs && typeof raw.knobs === "object" ? raw.knobs : {};
  Object.keys(LOOK_KNOBS).forEach(function (knob) {
    const value = knownLookValue(knob, knobs[knob]);
    if (value) clean.knobs[knob] = value;
  });
  return clean;
}

function readLook() {
  try {
    return sanitizeLook(JSON.parse(localStorage.getItem(LOOK_KEY) || "null"));
  } catch {
    // Private windows and locked-down desktop profiles can refuse storage, and
    // a hand-edited value is not worth a blank page.
    return sanitizeLook(null);
  }
}

function writeLook() {
  try {
    localStorage.setItem(LOOK_KEY, JSON.stringify(lookChoice));
  } catch { /* The choice still applies to this page. */ }
}

/** Every knob's value once the preset and the student's own overrides are layered on the defaults. */
function effectiveLook() {
  return Object.assign({}, LOOK_DEFAULTS, LOOK_PRESETS[lookChoice.preset], lookChoice.knobs);
}

function applyLook() {
  const root = document.documentElement.dataset;
  if (lookChoice.preset === "default") delete root.preset;
  else root.preset = lookChoice.preset;
  const look = effectiveLook();
  Object.keys(LOOK_KNOBS).forEach(function (knob) {
    // A knob at its default leaves no attribute behind, so the base rules apply.
    if (look[knob] === LOOK_DEFAULTS[knob]) delete root[knob];
    else root[knob] = look[knob];
  });
  return look;
}

/** Keep knobs the student set by hand. The preset fills in only the ones they left alone. */
function choosePreset(name) {
  const preset = Object.prototype.hasOwnProperty.call(LOOK_PRESETS, name) ? name : "default";
  lookChoice = { preset: preset, knobs: lookChoice.knobs || {} };
  writeLook();
  return applyLook();
}

function isDevicePreset(name) {
  return Object.prototype.hasOwnProperty.call(LOOK_PRESETS, name) && name !== "default";
}

function lookMenuValue(pack) {
  if (lookChoice.preset && lookChoice.preset !== "default") return lookChoice.preset;
  if (pack) return pack;
  if (typeof prefs !== "undefined" && prefs.theme_pack) return prefs.theme_pack;
  return "system";
}

function lookMenuPack(value, pack) {
  if (isDevicePreset(value)) {
    return typeof knownPack === "function" ? knownPack(pack) : (pack || "system");
  }
  return typeof knownPack === "function" ? knownPack(value) : (value || "system");
}

function chooseLook(value) {
  if (isDevicePreset(value)) {
    choosePreset(value);
    if (typeof syncLookControls === "function") syncLookControls();
    return;
  }
  choosePreset("default");
  const pack = lookMenuPack(value, typeof prefs !== "undefined" ? prefs.theme_pack : "system");
  if (typeof prefs !== "undefined" && prefs.theme_pack === pack) {
    if (typeof applyAppearance === "function") applyAppearance();
    else if (typeof syncLookControls === "function") syncLookControls();
    return;
  }
  if (typeof choosePack === "function") return choosePack(value);
}

function setLookKnob(knob, value) {
  const chosen = knownLookValue(knob, value);
  if (chosen) {
    lookChoice.knobs[knob] = chosen;
    writeLook();
  }
  return applyLook();
}

lookChoice = readLook();
applyLook();
