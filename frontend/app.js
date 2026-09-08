const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const START_HOUR = 6;
const END_HOUR = 23;
const PRIORITY_LABEL = { 1: "test", 2: "quiz", 3: "homework", 4: "reading" };
const STORAGE_KEY = "flexweek.week.v1";

const weekEl = document.getElementById("week");
const flexibleEl = document.getElementById("flexible");
const statusEl = document.getElementById("status");
const solveEl = document.getElementById("solve");
const debugEl = document.getElementById("debug");
const debugStatsEl = document.getElementById("debug-stats");
const debugUnplacedEl = document.getElementById("debug-unplaced");
const flexNoteEl = document.getElementById("flex-note");
const formEl = document.getElementById("block-form");
const formErrorEl = document.getElementById("form-error");
const formHeadingEl = document.getElementById("form-heading");
const formDeleteEl = document.getElementById("form-delete");
const lockedFieldsEl = document.getElementById("f-locked-fields");
const flexFieldsEl = document.getElementById("f-flex-fields");
const startEl = document.getElementById("f-start");
const dueTimeEl = document.getElementById("f-due-time");

function hourRange() {
  const hours = [];
  for (let hour = START_HOUR; hour < END_HOUR; hour += 1) hours.push(hour);
  return hours;
}

function pad(n) {
  return String(n).padStart(2, "0");
}

// A week_start is a calendar label, not an instant. `new Date("2026-09-07")`
// reads the string as UTC and lands on the day before west of Greenwich, so
// every helper below builds and reads dates through explicit numeric parts.
function parseDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value));
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return date;
}

function isoDate(date) {
  return date.getUTCFullYear() + "-" + pad(date.getUTCMonth() + 1) + "-" + pad(date.getUTCDate());
}

function mondayOf(value) {
  const date = parseDate(value);
  if (!date) return "";
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return isoDate(date);
}

function currentWeekStart() {
  const now = new Date();
  return mondayOf(now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate()));
}

function isWeekStart(value) {
  const date = parseDate(value);
  if (!date) return false;
  const year = date.getUTCFullYear();
  return date.getUTCDay() === 1 && year >= 2000 && year <= 2099;
}

function dateForDay(weekStart, dayIndex) {
  const date = parseDate(weekStart);
  if (!date || !Number.isInteger(dayIndex) || dayIndex < 0 || dayIndex > 6) return "";
  date.setUTCDate(date.getUTCDate() + dayIndex);
  return isoDate(date);
}

function shiftWeek(weekStart, weeksAhead) {
  const date = parseDate(weekStart);
  if (!date) return "";
  date.setUTCDate(date.getUTCDate() + weeksAhead * 7);
  return isoDate(date);
}

function shortDate(value) {
  const date = parseDate(value);
  return date ? MONTHS[date.getUTCMonth()] + " " + date.getUTCDate() : "";
}

function weekLabel(weekStart) {
  return "Week of " + shortDate(weekStart) + ", " + String(weekStart).slice(0, 4);
}

function parseStart(start) {
  const [h, m] = start.split(":").map(Number);
  return h * 60 + m;
}

function hourHeightRem() {
  const raw = getComputedStyle(document.documentElement).getPropertyValue("--hour-h");
  const value = parseFloat(raw);
  return Number.isFinite(value) ? value : 2.75;
}

function setStatus(msg) {
  statusEl.textContent = msg || "";
}

function slotTimes() {
  const times = [];
  for (let min = START_HOUR * 60; min < END_HOUR * 60; min += 15) {
    times.push(pad(Math.floor(min / 60)) + ":" + pad(min % 60));
  }
  return times;
}

function fillTimeSelect(select, includeBlank) {
  select.innerHTML = "";
  if (includeBlank) {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "—";
    select.appendChild(blank);
  }
  slotTimes().forEach((time) => {
    const opt = document.createElement("option");
    opt.value = time;
    opt.textContent = time;
    select.appendChild(opt);
  });
}

function isValidWeek(data) {
  if (!data || typeof data !== "object" || !Array.isArray(data.blocks)) return false;
  return data.blocks.every(function (block) {
    if (!block || typeof block !== "object") return false;
    if (block.kind !== "locked" && block.kind !== "flexible") return false;
    if (typeof block.title !== "string" || !block.title.trim()) return false;
    if (typeof block.duration_min !== "number" || block.duration_min <= 0 || block.duration_min % 15 !== 0) {
      return false;
    }
    if (!Array.isArray(block.days) || !block.days.length) return false;
    if (block.days.some(function (day) { return day < 0 || day > 6; })) return false;
    if (block.kind === "locked") {
      if (typeof block.start !== "string" || !/^\d{2}:\d{2}$/.test(block.start)) return false;
    }
    return true;
  });
}

function readWeek() {
  let raw;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch (err) {
    return null;
  }
  if (!raw) return null;
  try {
    const data = JSON.parse(raw);
    if (!isValidWeek(data)) return null;
    return data.blocks;
  } catch (err) {
    return null;
  }
}

let account = null;
let epoch = 0;
let saving = false;
let suspendedDraft = null;

// One record per week, keyed by its Monday. Blocks, revision, unsaved edits and
// a conflict all belong to the week they came from: a single global revision
// would let a save carry one week's blocks under another week's number.
const weeks = new Map();
let selectedWeek = currentWeekStart();
let savedWeeks = [];

function weekState(weekStart = selectedWeek) {
  let state = weeks.get(weekStart);
  if (!state) {
    state = { blocks: [], revision: 0, dirty: false, conflict: false };
    weeks.set(weekStart, state);
  }
  return state;
}

function dirtyWeeks() {
  return Array.from(weeks.keys()).filter(function (weekStart) { return weeks.get(weekStart).dirty; });
}

const authPanel = document.getElementById("auth-panel");
const planner = document.getElementById("planner");
const saveActions = document.getElementById("save-actions");
const themeEl = document.getElementById("theme");
const weekLabelEl = document.getElementById("week-label");
const weekJumpEl = document.getElementById("week-jump");
const channel = typeof BroadcastChannel === "function" ? new BroadcastChannel("flexweek.session") : null;

function lockEditor(locked) {
  planner.querySelectorAll("button, input, select").forEach(el => { el.disabled = locked; });
  solveEl.disabled = locked;
  document.getElementById("import-week").disabled = locked;
}

function signedOut(message = "Sign in to open your week.", preserve = true) {
  const pending = account ? dirtyWeeks() : [];
  if (preserve && pending.length) {
    suspendedDraft = { userId: account.id, weeks: pending.map(function (weekStart) {
      const state = weekState(weekStart);
      return { weekStart: weekStart, blocks: structuredClone(state.blocks), revision: state.revision };
    }) };
  }
  epoch += 1;
  account = null;
  weeks.clear();
  savedWeeks = [];
  selectedWeek = currentWeekStart();
  saving = false;
  weekEl.replaceChildren();
  flexibleEl.replaceChildren();
  debugStatsEl.textContent = "";
  debugUnplacedEl.replaceChildren();
  formEl.reset();
  closeForm();
  planner.hidden = true;
  debugEl.hidden = true;
  authPanel.hidden = false;
  document.getElementById("account-controls").hidden = true;
  document.getElementById("account-name").textContent = "";
  document.getElementById("import-panel").hidden = true;
  saveActions.hidden = true;
  document.documentElement.dataset.theme = "nocturne";
  lockEditor(false);
  setStatus(message);
}

async function api(path, options = {}, protectedRequest = true) {
  const requestEpoch = epoch;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {
      ...options,
      credentials: "same-origin", cache: "no-store", signal: controller.signal,
      headers: { "Content-Type": "application/json", "X-FlexWeek-Request": "1",
        ...(account && protectedRequest ? { "X-FlexWeek-Account": String(account.id) } : {}) },
    });
    if (requestEpoch !== epoch) throw new Error("Session changed. Please try again.");
    if (response.status === 401 && protectedRequest) {
      signedOut("Your session ended. Sign in again; unsaved edits can be restored to the same account.");
    }
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const error = new Error(data.detail || "Request failed. Please try again.");
      error.status = response.status;
      throw error;
    }
    return response.status === 204 ? null : await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Request timed out. Check your connection and retry.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function saveWeek() {
  if (!account || saving) return false;
  // The week on screen when the save starts owns this request, so a response
  // that lands later cannot be applied to a different week.
  const weekStart = selectedWeek;
  const state = weekState(weekStart);
  state.dirty = true;
  saveActions.hidden = false;
  if (state.conflict) {
    setStatus("Unsaved changes. Download your draft, then reload the newer saved week.");
    return false;
  }
  const saveEpoch = epoch;
  saving = true;
  lockEditor(true);
  document.getElementById("retry-save").disabled = true;
  setStatus("Saving…");
  try {
    const data = await api("/api/week", { method: "PUT", body: JSON.stringify({
      week_start: weekStart, blocks: state.blocks, revision: state.revision,
    }) });
    if (saveEpoch !== epoch) return false;
    state.revision = data.revision;
    state.dirty = false;
    saveActions.hidden = true;
    rememberSavedWeek(weekStart);
    setStatus("Saved · " + weekSummary());
    return true;
  } catch (error) {
    if (saveEpoch !== epoch) return false;
    state.conflict = error.status === 409;
    setStatus("Not saved. " + error.message);
    return false;
  } finally {
    if (saveEpoch === epoch) {
      saving = false;
      lockEditor(false);
      document.getElementById("retry-save").disabled = state.conflict;
    }
  }
}

async function loadAccount(identity) {
  epoch += 1;
  const loadEpoch = epoch;
  account = identity;
  const asked = currentWeekStart();
  try {
    const [week, saved, preferences] = await Promise.all([
      api("/api/week?week_start=" + asked), api("/api/weeks"), api("/api/preferences"),
    ]);
    if (loadEpoch !== epoch) return;
    weeks.clear();
    savedWeeks = Array.isArray(saved.week_start) ? saved.week_start.slice() : [];
    selectedWeek = isWeekStart(week.week_start) ? week.week_start : asked;
    const state = weekState();
    state.blocks = week.blocks;
    state.revision = week.revision;
    if (suspendedDraft && suspendedDraft.userId === account.id) {
      suspendedDraft.weeks.forEach(function (draft) {
        const target = weekState(draft.weekStart);
        target.blocks = draft.blocks;
        // Only the week just fetched has a known server revision to compare.
        target.conflict = draft.weekStart === selectedWeek && draft.revision !== target.revision;
        target.revision = draft.revision;
        target.dirty = true;
      });
    }
    suspendedDraft = null;
    themeEl.value = preferences.theme;
    document.documentElement.dataset.theme = preferences.theme;
    authPanel.hidden = true;
    planner.hidden = false;
    document.getElementById("account-controls").hidden = false;
    document.getElementById("account-name").textContent = identity.username;
    saveActions.hidden = !state.dirty;
    document.getElementById("retry-save").disabled = state.conflict;
    lockEditor(false);
    renderWeekNav();
    renderWeek();
    setStatus(state.dirty ? "Unsaved edits restored. " + (state.conflict ? "Download your draft and reload the newer week." : "Press Retry save.") : weekStatus());
    try {
      document.getElementById("import-panel").hidden = !localStorage.getItem(STORAGE_KEY);
    } catch { document.getElementById("import-panel").hidden = true; }
  } catch (error) {
    if (loadEpoch === epoch) signedOut("Could not open your week. " + error.message);
  }
}

function rememberSavedWeek(weekStart) {
  if (savedWeeks.indexOf(weekStart) !== -1) return;
  savedWeeks = savedWeeks.concat([weekStart]).sort();
  renderWeekNav();
}

function renderWeekNav() {
  weekLabelEl.textContent = weekLabel(selectedWeek);
  // A week holding unsaved edits is not saved on the server yet, so list it too
  // or the only way back to it would be the arrows.
  const listed = savedWeeks.concat([selectedWeek], dirtyWeeks()).filter(function (weekStart, index, all) {
    return all.indexOf(weekStart) === index;
  }).sort();
  weekJumpEl.innerHTML = "";
  listed.forEach(function (weekStart) {
    const option = document.createElement("option");
    option.value = weekStart;
    option.textContent = weekLabel(weekStart);
    weekJumpEl.appendChild(option);
  });
  weekJumpEl.value = selectedWeek;
}

function weekStatus() {
  const state = weekState();
  const stranded = dirtyWeeks().filter(function (weekStart) { return weekStart !== selectedWeek; });
  const note = stranded.length ? " · Unsaved edits kept in " + stranded.map(shortDate).join(", ") : "";
  if (state.dirty) return "Unsaved edits in this week. Press Retry save." + note;
  if (!state.blocks.length && savedWeeks.length && savedWeeks.indexOf(selectedWeek) === -1) {
    return "This week is empty. Your saved weeks are in the list." + note;
  }
  return "Saved · " + weekSummary() + note;
}

function showWeek(weekStart) {
  selectedWeek = weekStart;
  const state = weekState();
  closeForm();
  // The debug panel and the note under it describe the week being left.
  debugEl.hidden = true;
  flexNoteEl.textContent = "Press Solve to place these around school and sports.";
  saveActions.hidden = !state.dirty;
  document.getElementById("retry-save").disabled = state.conflict;
  renderWeekNav();
  renderWeek();
  setStatus(weekStatus());
}

async function selectWeek(weekStart) {
  if (!account || saving || weekStart === selectedWeek) return;
  if (!isWeekStart(weekStart)) {
    setStatus("That is not a Monday, so it cannot open as a week.");
    return;
  }
  const known = weeks.get(weekStart);
  // Refetching a week that holds unsaved edits would overwrite them.
  if (known && known.dirty) {
    showWeek(weekStart);
    return;
  }
  const selectEpoch = epoch;
  saving = true;
  lockEditor(true);
  setStatus("Opening " + weekLabel(weekStart) + "…");
  try {
    const data = await api("/api/week?week_start=" + weekStart);
    if (selectEpoch !== epoch) return;
    const opened = isWeekStart(data.week_start) ? data.week_start : weekStart;
    const state = weekState(opened);
    state.blocks = data.blocks;
    state.revision = data.revision;
    state.dirty = false;
    state.conflict = false;
    showWeek(opened);
  } catch (error) {
    // The week did not change, so put the picker back on the one still shown.
    if (selectEpoch === epoch) { renderWeekNav(); setStatus("Could not open that week. " + error.message); }
  } finally {
    if (selectEpoch === epoch) { saving = false; lockEditor(false); }
  }
}

function newId() {
  return "b-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 6);
}

function weekSummary() {
  const blocks = weekState().blocks;
  const locked = blocks.filter(function (b) { return b.kind === "locked"; }).length;
  const flex = blocks.filter(function (b) { return b.kind === "flexible"; }).length;
  return locked + " locked, " + flex + " flexible";
}

function renderWeek() {
  buildGrid(weekState().blocks);
}

function buildGrid(blocks) {
  weekEl.innerHTML = "";
  const corner = document.createElement("div");
  corner.className = "corner";
  weekEl.appendChild(corner);
  DAYS.forEach((day, index) => {
    const head = document.createElement("div");
    head.className = "day-head";
    const name = document.createElement("span");
    name.textContent = day;
    head.appendChild(name);
    const date = document.createElement("span");
    date.className = "day-date";
    date.textContent = shortDate(dateForDay(selectedWeek, index));
    head.appendChild(date);
    weekEl.appendChild(head);
  });

  const hours = hourRange();
  const hourH = hourHeightRem();
  const cells = Array.from({ length: 7 }, () => []);

  hours.forEach((hour) => {
    const label = document.createElement("div");
    label.className = "hour";
    label.textContent = `${pad(hour)}:00`;
    weekEl.appendChild(label);
    for (let day = 0; day < 7; day += 1) {
      const cell = document.createElement("div");
      cell.className = "cell";
      weekEl.appendChild(cell);
      cells[day].push(cell);
    }
  });

  const visibleEnd = END_HOUR * 60;
  const visibleStart = START_HOUR * 60;

  blocks.filter((b) => b.start).forEach((block) => {
    block.days.forEach((day) => {
      const startMin = parseStart(block.start);
      const endMin = Math.min(visibleEnd, startMin + (block.duration_min || 0));
      const clippedStart = Math.max(visibleStart, startMin);
      if (endMin <= clippedStart) return;

      const topHour = Math.floor(clippedStart / 60);
      const row = topHour - START_HOUR;
      if (row < 0 || row >= hours.length) return;

      const offsetMin = clippedStart - topHour * 60;
      const el = document.createElement("div");
      el.className = "block" + (block.kind === "flexible" ? " flex-block" : "");
      el.dataset.id = block.id;
      el.style.top = `${(offsetMin / 60) * hourH}rem`;
      el.style.height = `${Math.max(((endMin - clippedStart) / 60) * hourH, 1.1)}rem`;
      el.title = block.title + (block.course ? " · " + block.course : "") + " (click to edit)";

      const title = document.createElement("div");
      title.className = "title";
      title.textContent = block.title;
      el.appendChild(title);

      const sub = document.createElement("div");
      sub.className = "sub";
      sub.textContent = block.duration_min + " min";
      el.appendChild(sub);

      el.addEventListener("click", function (event) {
        event.stopPropagation();
        const source = weekState().blocks.find(function (item) { return item.id === block.id; });
        if (source) openForm(source.kind, source);
      });

      cells[day][row].appendChild(el);
    });
  });

  renderFlexible(blocks.filter((b) => b.kind === "flexible" && !b.start));
}

function renderFlexible(flex) {
  flexibleEl.innerHTML = "";
  if (!flex.length) {
    const empty = document.createElement("li");
    empty.textContent = "None unplaced.";
    flexibleEl.appendChild(empty);
    return;
  }

  flex.forEach((block) => {
    const li = document.createElement("li");
    li.className = "task-card";
    li.dataset.id = block.id;
    const name = document.createElement("strong");
    name.textContent = block.title;
    li.appendChild(name);

    const pills = document.createElement("div");
    pills.className = "pills";

    function pill(text) {
      const span = document.createElement("span");
      span.className = "pill";
      span.textContent = text;
      pills.appendChild(span);
    }

    pill(block.duration_min + " min");
    pill(PRIORITY_LABEL[block.priority] || "P" + block.priority);
    if (block.energy) pill(block.energy);
    if (block.course) pill(block.course);
    if (block.latest) pill("due " + block.latest);

    li.appendChild(pills);
    li.addEventListener("click", function () {
      const source = weekState().blocks.find(function (item) { return item.id === block.id; });
      if (source) openForm(source.kind, source);
    });
    flexibleEl.appendChild(li);
  });
}

function renderDebug(trace) {
  debugEl.hidden = false;
  const placedFlex = (trace.placed || []).filter((b) => b.kind === "flexible").length;
  debugStatsEl.textContent =
    "solve_ms " +
    Number(trace.solve_ms).toFixed(1) +
    " · placed " +
    placedFlex +
    " · unplaced " +
    (trace.unplaced || []).length +
    (trace.complete ? " · complete" : " · incomplete");
  debugUnplacedEl.innerHTML = "";
  const reasonById = {};
  (trace.moves || []).forEach((move) => {
    reasonById[move.block_id] = move.reason;
  });
  (trace.unplaced || []).forEach((block) => {
    const li = document.createElement("li");
    li.textContent = block.title + (reasonById[block.id] ? " · " + reasonById[block.id] : "");
    debugUnplacedEl.appendChild(li);
  });
  if (!(trace.unplaced || []).length) {
    const li = document.createElement("li");
    li.textContent = "All flexible tasks placed.";
    debugUnplacedEl.appendChild(li);
  }
}

function showFormError(msg) {
  if (!msg) {
    formErrorEl.hidden = true;
    formErrorEl.textContent = "";
    return;
  }
  formErrorEl.hidden = false;
  formErrorEl.textContent = msg;
}

function selectedDays() {
  return Array.from(formEl.querySelectorAll('input[name="f-day"]:checked')).map(function (el) {
    return Number(el.value);
  });
}

function setSelectedDays(days) {
  formEl.querySelectorAll('input[name="f-day"]').forEach(function (el) {
    el.checked = days.indexOf(Number(el.value)) !== -1;
  });
}

function parseLatest(latest) {
  if (!latest) return { day: "", time: "" };
  const parts = latest.trim().split(/\s+/);
  if (parts.length >= 2) {
    const name = parts[0].toLowerCase();
    const idx = DAY_FULL.findIndex(function (day) {
      return day.toLowerCase() === name || day.slice(0, 3).toLowerCase() === name.slice(0, 3);
    });
    return { day: idx >= 0 ? String(idx) : "", time: parts[parts.length - 1] };
  }
  return { day: "", time: parts[0] || "" };
}

function openForm(kind, block) {
  if (!account || saving) return;
  const editing = Boolean(block);
  formEl.hidden = false;
  showFormError("");
  document.getElementById("f-kind").value = kind;
  document.getElementById("f-id").value = editing ? block.id : "";
  formHeadingEl.textContent = (editing ? "Edit " : "Add ") + (kind === "locked" ? "locked" : "task");
  formDeleteEl.hidden = !editing;
  lockedFieldsEl.hidden = kind !== "locked";
  flexFieldsEl.hidden = kind !== "flexible";

  document.getElementById("f-title").value = editing ? block.title : "";
  document.getElementById("f-course").value = editing && block.course ? block.course : "";
  document.getElementById("f-duration").value = editing ? String(block.duration_min) : "60";
  setSelectedDays(editing ? block.days : []);
  startEl.value = editing && block.start ? block.start : "16:00";
  document.getElementById("f-priority").value = editing && block.priority ? String(block.priority) : "3";
  document.getElementById("f-energy").value = editing && block.energy ? block.energy : "medium";
  const latest = parseLatest(editing ? block.latest : "");
  document.getElementById("f-due-day").value = latest.day;
  dueTimeEl.value = latest.time || "21:00";
  document.getElementById("f-title").focus();
}

function closeForm() {
  formEl.hidden = true;
  showFormError("");
}

function durationError(value) {
  const n = Number(value);
  if (!Number.isInteger(n) || n <= 0 || n % 15 !== 0) {
    return "Duration must be a positive multiple of 15 minutes.";
  }
  return "";
}

formEl.addEventListener("submit", function (event) {
  event.preventDefault();
  if (!account || saving) return;
  const kind = document.getElementById("f-kind").value;
  const title = document.getElementById("f-title").value.trim();
  const durationMsg = durationError(document.getElementById("f-duration").value);
  const days = selectedDays();
  if (!title) {
    showFormError("Give this block a title.");
    return;
  }
  if (durationMsg) {
    showFormError(durationMsg);
    return;
  }
  if (!days.length) {
    showFormError("Pick at least one day.");
    return;
  }
  if (kind === "locked" && !startEl.value) {
    showFormError("Locked blocks need a start time.");
    return;
  }

  const id = document.getElementById("f-id").value || newId();
  const blocks = weekState().blocks;
  const existing = blocks.findIndex(function (item) { return item.id === id; });
  const block = {
    id: id,
    title: title,
    kind: kind,
    duration_min: Number(document.getElementById("f-duration").value),
    days: days,
    priority: Number(document.getElementById("f-priority").value) || 3,
    energy: document.getElementById("f-energy").value || "medium",
    course: document.getElementById("f-course").value.trim() || null,
    earliest: null,
    latest: null,
    start: kind === "locked" ? startEl.value : null,
  };
  if (kind === "flexible") {
    const dueDay = document.getElementById("f-due-day").value;
    const dueTime = dueTimeEl.value;
    if (dueDay !== "" && dueTime) {
      block.latest = DAY_FULL[Number(dueDay)] + " " + dueTime;
    }
  }

  if (existing >= 0) blocks[existing] = block;
  else blocks.push(block);

  closeForm();
  debugEl.hidden = true;
  flexNoteEl.textContent = "Press Solve to place these around school and sports.";
  saveWeek();
  renderWeek();
});

document.getElementById("form-cancel").addEventListener("click", closeForm);

formDeleteEl.addEventListener("click", function () {
  if (!account || saving) return;
  const id = document.getElementById("f-id").value;
  const state = weekState();
  state.blocks = state.blocks.filter(function (item) { return item.id !== id; });
  closeForm();
  debugEl.hidden = true;
  saveWeek();
  renderWeek();
});

document.getElementById("add-locked").addEventListener("click", function () {
  openForm("locked", null);
});
document.getElementById("add-flexible").addEventListener("click", function () {
  openForm("flexible", null);
});
document.getElementById("new-week").addEventListener("click", function () {
  if (!account || saving || !confirm("Clear " + weekLabel(selectedWeek) + "? This will be saved to your account.")) return;
  weekState().blocks = [];
  closeForm();
  debugEl.hidden = true;
  flexNoteEl.textContent = "Add locked school or sports, then homework as tasks.";
  saveWeek();
  renderWeek();
});

async function solveWeek() {
  if (!account || saving) return;
  const solveEpoch = epoch;
  saving = true;
  lockEditor(true);
  setStatus("Solving…");
  try {
    const trace = await api("/api/solve", { method: "POST", body: JSON.stringify({ blocks: weekState().blocks }) });
    if (solveEpoch !== epoch) return;
    buildGrid(trace.placed || []);
    renderFlexible(trace.unplaced || []);
    renderDebug(trace);
    flexNoteEl.textContent = trace.unplaced.length ? "Unplaced after Solve — reasons below." : "All flexible tasks are on the grid.";
    setStatus((weekState().dirty ? "Unsaved week · " : "Saved week · ") + trace.placed.filter(b => b.kind === "flexible").length + " tasks placed");
  } catch (error) {
    if (solveEpoch === epoch) setStatus("Solve failed. " + error.message);
  } finally {
    if (solveEpoch === epoch) { saving = false; lockEditor(false); }
  }
}

document.getElementById("auth-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const action = event.submitter?.value || "login";
  const authEpoch = epoch;
  form.querySelectorAll("button").forEach(el => { el.disabled = true; });
  document.getElementById("auth-error").textContent = "";
  try {
    const identity = await api("/api/auth/" + action, { method: "POST", body: JSON.stringify({
      username: document.getElementById("username").value,
      password: document.getElementById("password").value,
    }) }, false);
    document.getElementById("password").value = "";
    channel?.postMessage("session-changed");
    await loadAccount(identity);
  } catch (error) {
    if (authEpoch === epoch) document.getElementById("auth-error").textContent = error.message;
  } finally { form.querySelectorAll("button").forEach(el => { el.disabled = false; }); }
});

document.getElementById("logout").addEventListener("click", async () => {
  if (saving || (dirtyWeeks().length && !confirm("Sign out and discard unsaved changes? Download the draft first if you need it."))) return;
  const logoutEpoch = epoch;
  try {
    await api("/api/auth/logout", { method: "POST" });
    suspendedDraft = null;
    signedOut("Signed out.", false);
    channel?.postMessage("session-changed");
  } catch (error) { if (logoutEpoch === epoch) setStatus("Sign out failed. " + error.message); }
});

if (channel) channel.onmessage = () => signedOut("The account session changed in another window. Sign in to continue.");

themeEl.addEventListener("change", async () => {
  const oldTheme = document.documentElement.dataset.theme;
  const themeEpoch = epoch;
  document.documentElement.dataset.theme = themeEl.value;
  themeEl.disabled = true;
  try { await api("/api/preferences", { method: "PUT", body: JSON.stringify({ theme: themeEl.value }) }); }
  catch (error) {
    if (themeEpoch === epoch) {
      themeEl.value = oldTheme;
      document.documentElement.dataset.theme = oldTheme;
      setStatus("Theme was not saved. " + error.message);
    }
  } finally { themeEl.disabled = false; }
});

document.getElementById("retry-save").addEventListener("click", saveWeek);
document.getElementById("reload-week").addEventListener("click", async () => {
  if (saving || !account || (weekState().dirty && !confirm("Discard unsaved edits and reload the saved week?"))) return;
  const reloadEpoch = epoch;
  const weekStart = selectedWeek;
  saving = true;
  lockEditor(true);
  try {
    const data = await api("/api/week?week_start=" + weekStart);
    if (reloadEpoch !== epoch) return;
    const state = weekState(weekStart);
    state.blocks = data.blocks;
    state.revision = data.revision;
    state.dirty = false;
    state.conflict = false;
    saveActions.hidden = true;
    closeForm();
    debugEl.hidden = true;
    renderWeek();
    setStatus("Reloaded saved week.");
  } catch (error) { if (reloadEpoch === epoch) setStatus(error.message); }
  finally { if (reloadEpoch === epoch) { saving = false; lockEditor(false); } }
});
document.getElementById("download-draft").addEventListener("click", () => {
  if (!account) return;
  const draft = { week_start: selectedWeek, blocks: weekState().blocks };
  const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "flexweek-unsaved-" + selectedWeek + ".json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
document.getElementById("import-week").addEventListener("click", async () => {
  if (!account || saving) return;
  const blocks = readWeek();
  const importStatus = document.getElementById("import-status");
  if (!blocks) {
    importStatus.textContent = "The browser week is invalid. It has been left untouched; your saved week is unchanged.";
    return;
  }
  if (!confirm("Import this device's old week into your account, replacing " + weekLabel(selectedWeek) + "?")) return;
  weekState().blocks = blocks;
  closeForm();
  debugEl.hidden = true;
  renderWeek();
  if (await saveWeek()) {
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* A retry replaces the same blocks. */ }
    document.getElementById("import-panel").hidden = true;
  }
});

async function reconnect() {
  if (account) return;
  const connectionEpoch = epoch;
  setStatus("Connecting…");
  try { await loadAccount(await api("/api/auth/me", {}, false)); }
  catch (error) {
    if (connectionEpoch === epoch) signedOut(error.status === 401 ? "Sign in to open your week." : "Connection failed. " + error.message);
  }
}
document.getElementById("reconnect").addEventListener("click", reconnect);
window.addEventListener("beforeunload", event => {
  if (dirtyWeeks().length) { event.preventDefault(); event.returnValue = ""; }
});
window.addEventListener("pageshow", event => { if (event.persisted) { signedOut(); reconnect(); } });
document.addEventListener("visibilitychange", async () => {
  if (document.hidden || !account) return;
  try { await api("/api/auth/me"); } catch { /* Session expiry is handled by api. */ }
});
solveEl.addEventListener("click", solveWeek);
document.getElementById("week-prev").addEventListener("click", () => selectWeek(shiftWeek(selectedWeek, -1)));
document.getElementById("week-next").addEventListener("click", () => selectWeek(shiftWeek(selectedWeek, 1)));
document.getElementById("week-today").addEventListener("click", () => selectWeek(currentWeekStart()));
weekJumpEl.addEventListener("change", () => selectWeek(weekJumpEl.value));
fillTimeSelect(startEl, false);
fillTimeSelect(dueTimeEl, true);
reconnect();
