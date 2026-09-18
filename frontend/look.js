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

/** One tap is the whole look, so choosing a preset drops any knob the student set by hand. */
function choosePreset(name) {
  lookChoice = { preset: Object.prototype.hasOwnProperty.call(LOOK_PRESETS, name) ? name : "default", knobs: {} };
  writeLook();
  return applyLook();
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
