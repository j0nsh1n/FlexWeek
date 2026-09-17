// Stage 5 comfort controls shared by the browser and desktop app.

const COMFORT_PRESETS = [
  { id: "short", label: "Short", timer_work_min: 15, timer_break_min: 15, timer_long_break_min: 30, timer_long_break_every: 4 },
  { id: "standard", label: "Standard", timer_work_min: 30, timer_break_min: 15, timer_long_break_min: 30, timer_long_break_every: 4 },
  { id: "long", label: "Long", timer_work_min: 45, timer_break_min: 15, timer_long_break_min: 30, timer_long_break_every: 4 },
];
const COMFORT_TIMER_IDS = {
  timer_work_min: "pref-timer-work",
  timer_break_min: "pref-timer-break",
  timer_long_break_min: "pref-timer-long-break",
  timer_long_break_every: "pref-timer-cadence",
};
const SIDEBAR_MIN = 200;
const SIDEBAR_MAX = 640;
let comfortPresets = COMFORT_PRESETS;
let lastSplitPreview = null;
let layoutSaveVersion = 0;
let layoutSaveRunning = false;
let layoutSaveWaiters = [];
let comfortReferenceEpoch = null;

function comfortElement(id) {
  return document.getElementById(id);
}

function clampComfort(value, minimum, maximum, fallback) {
  if (value === null || value === undefined || String(value).trim() === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(minimum, Math.min(maximum, Math.round(parsed))) : fallback;
}

function timerEdit() {
  return {
    timer_work_min: clampComfort(comfortElement("pref-timer-work").value, 1, 180, 30),
    timer_break_min: clampComfort(comfortElement("pref-timer-break").value, 1, 60, 15),
    timer_long_break_min: clampComfort(comfortElement("pref-timer-long-break").value, 1, 120, 30),
    timer_long_break_every: clampComfort(comfortElement("pref-timer-cadence").value, 2, 12, 4),
  };
}

function matchingTimerPreset(values) {
  return comfortPresets.find(function (preset) {
    return Object.keys(COMFORT_TIMER_IDS).every(function (key) { return preset[key] === values[key]; });
  }) || null;
}

function renderTimerPresetSelection() {
  const current = timerEdit();
  const match = matchingTimerPreset(current);
  document.querySelectorAll("[data-timer-preset]").forEach(function (button) {
    button.ariaPressed = String(Boolean(match && match.id === button.dataset.timerPreset));
  });
}

function renderTimerPresets(presets) {
  comfortPresets = Array.isArray(presets) && presets.length ? presets : COMFORT_PRESETS;
  const container = comfortElement("timer-presets");
  if (!container) return;
  container.replaceChildren();
  comfortPresets.forEach(function (preset) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary";
    button.dataset.timerPreset = preset.id;
    button.textContent = preset.label;
    button.addEventListener("click", function () {
      Object.keys(COMFORT_TIMER_IDS).forEach(function (key) {
        comfortElement(COMFORT_TIMER_IDS[key]).value = String(preset[key]);
      });
      hideSplitPreview();
      renderTimerPresetSelection();
    });
    container.appendChild(button);
  });
  renderTimerPresetSelection();
}

function hideSplitPreview() {
  lastSplitPreview = null;
  const result = comfortElement("timer-preview-result");
  if (result) result.hidden = true;
}

function splitSegmentText(segments) {
  return (segments || []).map(function (segment) {
    return segment.duration_min + " min " + (segment.role === "work" ? "focus" : "break");
  }).join(" + ");
}

async function previewTimerSplit() {
  const result = comfortElement("timer-preview-result");
  const message = comfortElement("timer-preview-message");
  const segments = comfortElement("timer-preview-segments");
  const useRounded = comfortElement("timer-use-rounded");
  const previewEpoch = epoch;
  const previewAccount = account && account.id;
  try {
    const preview = await api("/api/timer-split-preview", {
      method: "POST",
      body: JSON.stringify({
        duration_min: Number(comfortElement("timer-preview-duration").value),
        ...timerEdit(),
      }),
    });
    if (previewEpoch !== epoch || !account || account.id !== previewAccount) return null;
    lastSplitPreview = preview;
    message.textContent = preview.message || "These times already fit the 15-minute calendar grid.";
    const plan = splitSegmentText(preview.segments);
    segments.textContent = plan ? plan + " · " + preview.total_min + " min on the calendar" : "";
    useRounded.hidden = !preview.rounded;
    result.hidden = false;
    return preview;
  } catch (error) {
    if (previewEpoch !== epoch || !account || account.id !== previewAccount) return null;
    lastSplitPreview = null;
    message.textContent = "Could not preview the split. " + error.message;
    segments.textContent = "";
    useRounded.hidden = true;
    result.hidden = false;
    return null;
  }
}

function useRoundedTimerPreview() {
  if (!lastSplitPreview) return;
  ["timer_work_min", "timer_break_min", "timer_long_break_min"].forEach(function (key) {
    comfortElement(COMFORT_TIMER_IDS[key]).value = String(lastSplitPreview[key]);
  });
  renderTimerPresetSelection();
  comfortElement("timer-preview-message").textContent = "Rounded times are ready to save.";
  comfortElement("timer-use-rounded").hidden = true;
}

function readComfortEdit() {
  return {
    alert_volume: clampComfort(comfortElement("pref-alert-volume").value, 0, 100, 80),
    end_chime: comfortElement("pref-end-chime").checked,
    tray_notifications: comfortElement("pref-tray-notifications").checked,
    start_at_login: comfortElement("pref-start-at-login").checked,
    preferred_view: comfortElement("pref-preferred-view").value || null,
    sidebar_collapsed: Boolean(prefs.sidebar_collapsed),
    sidebar_width_px: prefs.sidebar_width_px !== null && prefs.sidebar_width_px !== undefined &&
      Number.isFinite(Number(prefs.sidebar_width_px)) ? Number(prefs.sidebar_width_px) : null,
  };
}

async function prepareComfortSave(next) {
  if (!next.auto_split_pomodoro) return null;
  const offGrid = [next.timer_work_min, next.timer_break_min, next.timer_long_break_min]
    .some(function (value) { return value % 15 !== 0; });
  if (!offGrid) return null;
  const preview = await previewTimerSplit();
  return preview
    ? "Automatic calendar splitting needs 15-minute times. Review the preview, choose Use rounded times, then save again."
    : "Automatic calendar splitting needs 15-minute times. Preview the calendar split before saving.";
}

function updateVolumeOutput() {
  const value = clampComfort(comfortElement("pref-alert-volume").value, 0, 100, 80);
  comfortElement("pref-alert-volume-value").textContent = value + "%";
}

function applySidebarLayout() {
  const plannerElement = comfortElement("planner");
  const toggle = comfortElement("sidebar-toggle");
  const resizer = comfortElement("sidebar-resizer");
  const collapsed = Boolean(prefs.sidebar_collapsed);
  const width = prefs.sidebar_width_px !== null && prefs.sidebar_width_px !== undefined &&
    Number.isFinite(Number(prefs.sidebar_width_px))
    ? clampComfort(prefs.sidebar_width_px, SIDEBAR_MIN, SIDEBAR_MAX, 320) : null;
  plannerElement.dataset.sidebarCollapsed = String(collapsed);
  if (width === null) {
    if (typeof plannerElement.style.removeProperty === "function") plannerElement.style.removeProperty("--sidebar-width");
    else plannerElement.style["--sidebar-width"] = "";
  } else if (typeof plannerElement.style.setProperty === "function") {
    plannerElement.style.setProperty("--sidebar-width", width + "px");
  } else {
    plannerElement.style["--sidebar-width"] = width + "px";
  }
  toggle.textContent = collapsed ? "Show sidebar" : "Hide sidebar";
  toggle.ariaExpanded = String(!collapsed);
  resizer.ariaValueNow = String(width || 320);
}

function applyComfortPreferences() {
  const values = {
    "pref-alert-volume": prefs.alert_volume,
    "pref-preferred-view": prefs.preferred_view || "",
  };
  Object.keys(values).forEach(function (id) { comfortElement(id).value = String(values[id]); });
  comfortElement("pref-end-chime").checked = prefs.end_chime;
  comfortElement("pref-tray-notifications").checked = prefs.tray_notifications;
  comfortElement("pref-start-at-login").checked = prefs.start_at_login;
  updateVolumeOutput();
  renderTimerPresetSelection();
  applySidebarLayout();
}

async function saveComfortLayout() {
  layoutSaveVersion += 1;
  if (layoutSaveRunning || !account) return;
  layoutSaveRunning = true;
  try {
    while (account) {
      const requested = layoutSaveVersion;
      const saveEpoch = epoch;
      try {
        await api("/api/preferences", { method: "PUT", body: JSON.stringify(preferencesPayload()) });
        if (saveEpoch !== epoch) return;
      } catch (error) {
        if (saveEpoch === epoch) setStatus("Layout was not saved. " + error.message);
        return;
      }
      if (requested === layoutSaveVersion) return;
    }
  } finally {
    layoutSaveRunning = false;
    const waiters = layoutSaveWaiters;
    layoutSaveWaiters = [];
    waiters.forEach(function (resolve) { resolve(); });
  }
}

function waitForComfortLayoutSave() {
  if (!layoutSaveRunning) return Promise.resolve();
  return new Promise(function (resolve) { layoutSaveWaiters.push(resolve); });
}

function rememberPlannerView(next) {
  if (!account || (next !== "day" && next !== "week")) return;
  prefs.preferred_view = next;
  const select = comfortElement("pref-preferred-view");
  if (select) select.value = next;
  saveComfortLayout();
}

function toggleSidebar() {
  if (!account) return;
  prefs.sidebar_collapsed = !prefs.sidebar_collapsed;
  applySidebarLayout();
  saveComfortLayout();
}

function setSidebarWidth(width, save) {
  prefs.sidebar_width_px = clampComfort(width, SIDEBAR_MIN, SIDEBAR_MAX, 320);
  prefs.sidebar_collapsed = false;
  applySidebarLayout();
  if (save) saveComfortLayout();
}

function beginSidebarResize(event) {
  if (!account || prefs.sidebar_collapsed || (typeof matchMedia === "function" && matchMedia("(max-width: 800px)").matches)) return;
  const resizer = comfortElement("sidebar-resizer");
  const side = comfortElement("planner-sidebar");
  const startX = event.clientX;
  const startWidth = side.getBoundingClientRect().width || Number(prefs.sidebar_width_px) || 320;
  resizer.classList.add("is-resizing");
  if (resizer.setPointerCapture) resizer.setPointerCapture(event.pointerId);
  function move(moveEvent) { setSidebarWidth(startWidth - (moveEvent.clientX - startX), false); }
  function finish() {
    resizer.classList.remove("is-resizing");
    resizer.removeEventListener("pointermove", move);
    resizer.removeEventListener("pointerup", finish);
    resizer.removeEventListener("pointercancel", finish);
    saveComfortLayout();
  }
  resizer.addEventListener("pointermove", move);
  resizer.addEventListener("pointerup", finish);
  resizer.addEventListener("pointercancel", finish);
}

function resizeSidebarFromKeyboard(event) {
  const current = Number(prefs.sidebar_width_px) || comfortElement("planner-sidebar").getBoundingClientRect().width || 320;
  let next = null;
  if (event.key === "ArrowLeft") next = current + 16;
  if (event.key === "ArrowRight") next = current - 16;
  if (event.key === "Home") next = SIDEBAR_MIN;
  if (event.key === "End") next = SIDEBAR_MAX;
  if (next === null) return;
  event.preventDefault();
  setSidebarWidth(next, true);
}

function previewComfortAlert(kind) {
  const enabled = comfortElement("pref-reminder-sound").checked;
  const volume = clampComfort(comfortElement("pref-alert-volume").value, 0, 100, 80);
  const tone = kind === "reminder" ? "chime" : comfortElement("pref-preview-tone").value;
  const title = kind === "reminder" ? "Test reminder" : "Preview alert";
  const body = kind === "reminder" ? "Your next block starts in 5 minutes." : "This is how your selected alert sounds.";
  showReminderToast(title + " — " + body);
  if (enabled && volume > 0) soundOnce(tone, volume);
}

function renderReminderLimits(limits) {
  const list = comfortElement("reminder-limits");
  list.replaceChildren();
  ["web_open", "desktop_background", "spotify", "duplicate"].forEach(function (key) {
    if (!limits || !limits[key]) return;
    const item = document.createElement("li");
    item.textContent = limits[key];
    list.appendChild(item);
  });
  if (!list.children.length) {
    const item = document.createElement("li");
    item.textContent = "Reminder details could not be loaded.";
    list.appendChild(item);
  }
}

async function prepareComfortAccount() {
  if (!account || comfortReferenceEpoch === epoch) return;
  comfortReferenceEpoch = epoch;
  const loadEpoch = epoch;
  const results = await Promise.allSettled([api("/api/timer-presets"), api("/api/reminder-limits")]);
  if (loadEpoch !== epoch || !account) return;
  renderTimerPresets(results[0].status === "fulfilled" ? results[0].value.presets : COMFORT_PRESETS);
  renderReminderLimits(results[1].status === "fulfilled" ? results[1].value : null);
}

function clearComfortState() {
  layoutSaveVersion += 1;
  comfortReferenceEpoch = null;
  hideSplitPreview();
  comfortPresets = COMFORT_PRESETS;
  const plannerElement = comfortElement("planner");
  plannerElement.dataset.sidebarCollapsed = "false";
  if (typeof plannerElement.style.removeProperty === "function") plannerElement.style.removeProperty("--sidebar-width");
  else plannerElement.style["--sidebar-width"] = "";
}

comfortElement("timer-preview").addEventListener("click", previewTimerSplit);
comfortElement("timer-use-rounded").addEventListener("click", useRoundedTimerPreview);
Object.values(COMFORT_TIMER_IDS).forEach(function (id) {
  comfortElement(id).addEventListener("input", function () { hideSplitPreview(); renderTimerPresetSelection(); });
});
comfortElement("pref-alert-volume").addEventListener("input", updateVolumeOutput);
// Motion is a device setting, not an account one: it never reaches
// /api/preferences, because the preferences model has no field for it yet.
comfortElement("pref-motion").value = document.documentElement.dataset.motion;
comfortElement("pref-motion").addEventListener("change", function () {
  if (typeof rememberMotion === "function") rememberMotion(comfortElement("pref-motion").value);
});
comfortElement("test-reminder").addEventListener("click", function () { previewComfortAlert("reminder"); });
comfortElement("preview-alert").addEventListener("click", function () { previewComfortAlert("alert"); });
comfortElement("sidebar-toggle").addEventListener("click", toggleSidebar);
comfortElement("sidebar-resizer").addEventListener("pointerdown", beginSidebarResize);
comfortElement("sidebar-resizer").addEventListener("keydown", resizeSidebarFromKeyboard);
renderTimerPresets(COMFORT_PRESETS);
["settings-focus", "settings-notifications"].forEach(function (id) {
  comfortElement(id).addEventListener("toggle", function (event) {
    if (event.target.open) prepareComfortAccount();
  });
});
