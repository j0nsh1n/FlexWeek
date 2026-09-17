// How much the app animates, for this device only. Nothing here is sent to the
// account: the account-persisted setting arrives with the appearance contract.
// The stylesheet reads <html data-motion>; the system reduced-motion setting
// wins over any choice made here, so "off" and "reduce" mean the same thing.
const MOTION_KEY = "flexweek-motion";
const MOTION_LEVELS = ["off", "normal", "extra"];

function storedMotion() {
  try {
    return localStorage.getItem(MOTION_KEY);
  } catch {
    // Private windows and locked-down desktop profiles can refuse storage.
    return null;
  }
}

function applyMotion(level) {
  const chosen = MOTION_LEVELS.indexOf(level) === -1 ? "normal" : level;
  document.documentElement.dataset.motion = chosen;
  return chosen;
}

function rememberMotion(level) {
  const chosen = applyMotion(level);
  try {
    localStorage.setItem(MOTION_KEY, chosen);
  } catch { /* The choice still applies to this page. */ }
  return chosen;
}

applyMotion(storedMotion());
