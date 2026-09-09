const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const START_HOUR = 6;
const END_HOUR = 23;
const PRIORITY_LABEL = { 1: "test", 2: "quiz", 3: "homework", 4: "reading" };
const SNAP_MIN = 15;
const DAY_START_MIN = START_HOUR * 60;
const DAY_END_MIN = END_HOUR * 60;
const EDGE_PX = 8;
const CATEGORIES = [
  { id: "class", label: "School", color: "#3b82f6" },
  { id: "study", label: "Study", color: "#8b5cf6" },
  { id: "assignments", label: "Homework", color: "#ef4444" },
  { id: "exercise", label: "Sports", color: "#10b981" },
  { id: "extra", label: "Activity", color: "#ec4899" },
  { id: "meals", label: "Meals", color: "#f97316" },
  { id: "sleep", label: "Sleep", color: "#6366f1" },
  { id: "free", label: "Free", color: "#94a3b8" },
];

const EXPORT_FORMAT = "flexweek-week";
const EXPORT_VERSION = 1;
const REMINDER_WINDOW_MIN = 2;
const REMINDER_POLL_MS = 30000;

function isSeries(block) {
  return Boolean(block && Array.isArray(block.days) && block.days.length > 1);
}

function cloneBlock(block) {
  return JSON.parse(JSON.stringify(block));
}

function occurrenceDays(block) {
  if (block && block.kind === "flexible" && block.completed) {
    if (Number.isInteger(block.completed_day)) return [block.completed_day];
    if (Array.isArray(block.days) && block.days.length > 1) return [];
  }
  return block && Array.isArray(block.days) ? block.days : [];
}

function textLength(value) {
  return Array.from(value).length;
}

function occurrenceImportId(day, blockId) {
  const prefix = "occ-" + day + "-";
  const id = String(blockId);
  const legacy = prefix + id;
  if (textLength(legacy) <= 80) return legacy;
  let hash = 2166136261;
  for (const character of id) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  const suffix = "-" + (hash >>> 0).toString(16).padStart(8, "0");
  const available = 80 - textLength(prefix + suffix);
  return prefix + Array.from(id).slice(0, available).join("") + suffix;
}

function removeOccurrence(block, day) {
  if (!block || !Number.isInteger(day)) return block || null;
  const days = (block.days || []).filter(function (d) { return d !== day; });
  if (!days.length) return null;
  const next = cloneBlock(block);
  next.days = days;
  next.missed_days = (next.missed_days || []).filter(function (d) {
    return d !== day && days.indexOf(d) !== -1;
  });
  return next;
}

function applyBlockPatch(block, patch) {
  const next = cloneBlock(block);
  const keys = Object.keys(patch || {});
  for (let i = 0; i < keys.length; i += 1) {
    const key = keys[i];
    if (key === "id" || key === "kind") continue;
    next[key] = patch[key];
  }
  if (Array.isArray(next.days)) {
    next.days = Array.from(new Set(next.days)).filter(function (d) {
      return Number.isInteger(d) && d >= 0 && d <= 6;
    }).sort();
  }
  next.missed_days = (next.missed_days || []).filter(function (d) {
    return (next.days || []).indexOf(d) !== -1;
  });
  return next;
}

/** Edit one weekday of a multi-day locked block. Field changes split a new one-day block. */
function editOccurrence(block, day, patch) {
  if (!block || !Number.isInteger(day) || (block.days || []).indexOf(day) === -1) {
    return { series: block, split: null };
  }
  const patchObj = patch || {};
  const onlyMembership = Object.keys(patchObj).length === 0;
  if (onlyMembership) {
    return { series: removeOccurrence(block, day), split: null };
  }
  const current = { priority: 3, energy: "medium", course: null, category: null,
    completed: false, earliest: null, latest: null, ...block };
  if (Object.keys(patchObj).every(key => JSON.stringify(patchObj[key]) === JSON.stringify(current[key]))) {
    return { series: cloneBlock(block), split: null };
  }
  const series = removeOccurrence(block, day);
  const split = applyBlockPatch(block, patchObj);
  split.id = typeof newId === "function" ? newId() : ("occ-" + day + "-" + String(block.id));
  split.days = [day];
  split.missed_days = (block.missed_days || []).indexOf(day) !== -1 ? [day] : [];
  split.kind = block.kind;
  return { series: series, split: split };
}

function editSeries(block, patch) {
  return applyBlockPatch(block, patch || {});
}

function startAlertDue(startMin, nowMin, lead, windowMin) {
  const fireAt = Math.max(0, Number(startMin) - Math.max(0, Number(lead) || 0));
  const now = Number(nowMin);
  const window = Math.max(0, Number(windowMin) || 0);
  return now - window <= fireAt && fireAt <= now;
}

function reminderKey(weekStart, blockId, day, start) {
  return [weekStart, blockId, day, start].join("|");
}

function categoryLabel(category) {
  for (let i = 0; i < CATEGORIES.length; i += 1) {
    if (CATEGORIES[i].id === category) return CATEGORIES[i].label;
  }
  return "";
}

function exportWeekPayload(weekStart, blocks) {
  return {
    format: EXPORT_FORMAT,
    version: EXPORT_VERSION,
    week_start: weekStart,
    blocks: (blocks || []).map(function (block) { return cloneBlock(block); }),
  };
}

function presentationBlocks(state) {
  if (!state || !state.trace) return state ? state.blocks : [];
  const missed = state.blocks.filter(function (block) {
    return block.kind === "locked" && (block.missed_days || []).length;
  }).map(function (block) {
    return { ...block, days: block.missed_days.slice() };
  });
  return (state.trace.placed || []).concat(missed, state.trace.unplaced || []);
}

function exportDayPayload(weekStart, day, blocks) {
  const date = dateForDay(weekStart, day);
  const dayBlocks = (blocks || []).filter(function (block) {
    return occurrenceDays(block).indexOf(day) !== -1;
  }).map(function (block) {
    const copy = cloneBlock(block);
    copy.days = [day];
    if (copy.missed_days) {
      copy.missed_days = copy.missed_days.filter(function (d) { return d === day; });
    }
    return copy;
  });
  return {
    format: "flexweek-day",
    version: EXPORT_VERSION,
    week_start: weekStart,
    date: date,
    day: day,
    blocks: dayBlocks,
  };
}

function formatWeekExportText(weekStart, blocks) {
  const lines = ["FlexWeek — " + weekLabel(weekStart), ""];
  for (let day = 0; day < 7; day += 1) {
    const onDay = (blocks || []).filter(function (b) {
      return b.start && occurrenceDays(b).indexOf(day) !== -1;
    }).slice().sort(function (a, b) {
      return parseStart(a.start) - parseStart(b.start);
    });
    lines.push(DAYS[day] + " " + shortDate(dateForDay(weekStart, day)));
    if (!onDay.length) lines.push("  (empty)");
    onDay.forEach(function (block) {
      const end = formatMinute(parseStart(block.start) + block.duration_min);
      const done = block.completed ? " [done]" : "";
      const cat = block.category ? " [" + block.category + "]" : "";
      lines.push("  " + block.start + "-" + end + "  " + block.title + cat + done);
    });
    lines.push("");
  }
  const flex = (blocks || []).filter(function (b) { return b.kind === "flexible" && !b.start; });
  if (flex.length) {
    lines.push("Unplaced tasks");
    flex.forEach(function (block) {
      lines.push("  " + block.title + " (" + block.duration_min + " min)" + (block.completed ? " [done]" : ""));
    });
  }
  return lines.join("\n").trim() + "\n";
}

const MAX_IMPORT_BLOCKS = 100;
const ENERGIES = ["high", "medium", "low"];

/** Reject an import the server would reject, before any week state is touched.
    Mirrors the TimeBlock contract in backend/models.py; a payload that passes
    here must not come back 422. */
function importBlockError(block, index) {
  const at = "Block " + (index + 1);
  if (!block || typeof block !== "object" || Array.isArray(block)) return at + " is not a block.";
  if (typeof block.id !== "string" || !block.id || textLength(block.id) > 80) return at + " has a bad id.";
  if (typeof block.title !== "string" || !block.title.trim() || textLength(block.title) > 80) {
    return at + " has a bad title.";
  }
  if (block.kind !== "locked" && block.kind !== "flexible") return at + " has an unknown kind.";
  if (!Number.isInteger(block.duration_min) || block.duration_min <= 0
      || block.duration_min > 7140 || block.duration_min % SNAP_MIN !== 0) {
    return at + " needs a duration in whole 15-minute steps.";
  }
  if (!Array.isArray(block.days) || !block.days.length || block.days.length > 7) return at + " has bad days.";
  if (block.days.some(function (day) { return !Number.isInteger(day) || day < 0 || day > 6; })) {
    return at + " has bad days.";
  }
  if (new Set(block.days).size !== block.days.length) return at + " repeats a day.";
  if (block.priority !== undefined && [1, 2, 3, 4].indexOf(block.priority) === -1) {
    return at + " has a bad priority.";
  }
  if (block.energy !== undefined && ENERGIES.indexOf(block.energy) === -1) return at + " has a bad energy.";
  if (block.kind === "locked" && typeof block.start !== "string") return at + " is locked but has no start.";
  if (block.start !== undefined && block.start !== null) {
    if (typeof block.start !== "string" || !/^([01]\d|2[0-3]):[0-5]\d$/.test(block.start)) {
      return at + " has a bad start time.";
    }
    const startMin = parseStart(block.start);
    if (startMin % SNAP_MIN !== 0) return at + " must start on a 15-minute slot.";
    if (startMin < DAY_START_MIN || startMin + block.duration_min > DAY_END_MIN) {
      return at + " does not fit the visible day.";
    }
  }
  const texts = [["earliest", 40], ["latest", 40], ["course", 40], ["category", 32]];
  for (let i = 0; i < texts.length; i += 1) {
    const value = block[texts[i][0]];
    if (value === undefined || value === null) continue;
    if (typeof value !== "string" || textLength(value) > texts[i][1]) {
      return at + " has a bad " + texts[i][0] + ".";
    }
  }
  const boundPattern = /^(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) )?(?:[01]\d|2[0-3]):[0-5]\d$/;
  if ([block.earliest, block.latest].some(value => value != null && !boundPattern.test(value))) {
    return at + " has a bad deadline or earliest time.";
  }
  if (block.completed !== undefined && typeof block.completed !== "boolean") {
    return at + " has a bad completed flag.";
  }
  if (block.completed_day !== undefined && block.completed_day !== null) {
    if (!Number.isInteger(block.completed_day) || block.completed_day < 0 || block.completed_day > 6
      || block.kind !== "flexible" || block.completed !== true || !block.start
      || block.days.indexOf(block.completed_day) === -1) {
      return at + " has a completed day without a finished placement.";
    }
  }
  if (block.missed_days !== undefined) {
    const missed = block.missed_days;
    if (!Array.isArray(missed) || missed.length > 7) return at + " has bad missed days.";
    if (missed.some(function (day) { return !Number.isInteger(day) || day < 0 || day > 6; })) {
      return at + " has bad missed days.";
    }
    if (new Set(missed).size !== missed.length) return at + " repeats a missed day.";
    if (missed.length && block.kind !== "locked") return at + " marks missed days on a flexible task.";
    if (missed.some(function (day) { return block.days.indexOf(day) === -1; })) {
      return at + " misses a day it does not run on.";
    }
  }
  return null;
}

function importBlocksError(blocks) {
  if (blocks.length > MAX_IMPORT_BLOCKS) return "Export has more than " + MAX_IMPORT_BLOCKS + " blocks.";
  const seen = new Set();
  for (let i = 0; i < blocks.length; i += 1) {
    const problem = importBlockError(blocks[i], i);
    if (problem) return problem;
    if (seen.has(blocks[i].id)) return "Export repeats the id " + blocks[i].id + ".";
    seen.add(blocks[i].id);
  }
  return null;
}

function parseImportPayload(raw) {
  const text = String(raw || "").trim();
  if (!text) return { error: "Empty file." };
  let data;
  try { data = JSON.parse(text); }
  catch (err) { return { error: "Not valid JSON. Plain-text import is export-only." }; }
  if (!data || typeof data !== "object") return { error: "Invalid FlexWeek export." };
  if (data.format !== EXPORT_FORMAT && data.format !== "flexweek-day") {
    return { error: "Unrecognized export format." };
  }
  if (!Number.isInteger(data.version) || data.version < 1) return { error: "Export has no version." };
  if (data.version > EXPORT_VERSION) {
    return { error: "Export came from a newer FlexWeek (version " + data.version + ")." };
  }
  if (!Array.isArray(data.blocks)) return { error: "Export is missing blocks." };
  const weekStart = data.week_start;
  if (weekStart && !isWeekStart(weekStart)) return { error: "Export week_start must be a Monday." };
  // Validate every block before returning, so a bad file never reaches week state.
  const blockProblem = importBlocksError(data.blocks);
  if (blockProblem) return { error: blockProblem + " Nothing was imported." };
  if (data.format === "flexweek-day" && (
    !Number.isInteger(data.day) || data.day < 0 || data.day > 6
    || data.blocks.some(block => block.days.length !== 1 || block.days[0] !== data.day)
  )) return { error: "Day export must contain only its day in 0..6. Nothing was imported." };
  return {
    format: data.format,
    week_start: weekStart || null,
    day: Number.isInteger(data.day) ? data.day : null,
    blocks: data.blocks,
  };
}

function mergeImportedBlocks(existing, incoming, mode, day) {
  // mode: "replace" replaces all; "merge" upserts by id without dropping others
  if (mode === "replace") return (incoming || []).map(cloneBlock);
  const byId = Object.create(null);
  (existing || []).forEach(function (block) { byId[block.id] = cloneBlock(block); });
  (incoming || []).forEach(function (block) {
    if (!block || !block.id) return;
    const current = byId[block.id];
    const splitId = occurrenceImportId(day, block.id);
    const priorSplit = byId[splitId];
    // A day import refreshes one occurrence of a same-ID series; the other
    // weekdays of that series must survive the upsert.
    const importsOneDay = Number.isInteger(day)
      && (block.days || []).length === 1 && block.days[0] === day;
    if (current && importsOneDay && current.kind === "flexible" && isSeries(current)) {
      throw new Error("Day import cannot merge multi-day task " + block.id + ". Import the full week instead.");
    }
    if (current && block.kind === "locked" && current.kind === "locked"
      && importsOneDay && isSeries(current) && current.days.includes(day)) {
      if (priorSplit) throw new Error("Import would overwrite existing block " + splitId + ".");
      const kept = removeOccurrence(current, day);
      const split = cloneBlock(block);
      split.id = splitId;
      split.days = [day];
      split.missed_days = (split.missed_days || []).filter(function (d) { return d === day; });
      if (kept) byId[current.id] = kept; else delete byId[current.id];
      byId[split.id] = split;
      return;
    }
    if (current && block.kind === "locked" && current.kind === "locked"
      && importsOneDay && !current.days.includes(day) && priorSplit
      && (priorSplit.days || []).length === 1 && priorSplit.days[0] === day) {
      const split = cloneBlock(block);
      split.id = splitId;
      byId[splitId] = split;
      return;
    }
    byId[block.id] = cloneBlock(block);
  });
  return Object.keys(byId).map(function (id) { return byId[id]; });
}

function snapMinute(minute) {
  const m = Math.round(Number(minute) / SNAP_MIN) * SNAP_MIN;
  return Math.max(DAY_START_MIN, Math.min(DAY_END_MIN, m));
}

function formatMinute(minute) {
  const clamped = Math.max(DAY_START_MIN, Math.min(DAY_END_MIN, minute));
  return pad(Math.floor(clamped / 60)) + ":" + pad(clamped % 60);
}

function createDragRange(a, b) {
  let startMin = snapMinute(Math.min(a, b));
  let endMin = snapMinute(Math.max(a, b));
  if (endMin - startMin < SNAP_MIN) endMin = Math.min(DAY_END_MIN, startMin + SNAP_MIN);
  if (endMin - startMin < SNAP_MIN) return null;
  return { startMin: startMin, endMin: endMin };
}

function createClickRange(startMin, occupied) {
  const start = snapMinute(startMin);
  let end = Math.min(start + 60, DAY_END_MIN);
  const slots = (occupied || []).slice().sort(function (x, y) { return x.startMin - y.startMin; });
  for (let i = 0; i < slots.length; i += 1) {
    if (slots[i].startMin >= start && slots[i].startMin < end) {
      end = slots[i].startMin;
      break;
    }
  }
  if (end - start < SNAP_MIN) return null;
  return { startMin: start, endMin: end };
}

function moveRange(startMin, endMin, deltaMin) {
  const dur = endMin - startMin;
  let next = snapMinute(startMin + deltaMin);
  next = Math.max(DAY_START_MIN, Math.min(next, DAY_END_MIN - dur));
  return { startMin: next, endMin: next + dur };
}

function resizeTopRange(startMin, endMin, deltaMin) {
  let next = snapMinute(startMin + deltaMin);
  next = Math.max(DAY_START_MIN, Math.min(next, endMin - SNAP_MIN));
  return { startMin: next, endMin: endMin };
}

function resizeBottomRange(startMin, endMin, deltaMin) {
  let next = snapMinute(endMin + deltaMin);
  next = Math.min(DAY_END_MIN, Math.max(next, startMin + SNAP_MIN));
  return { startMin: startMin, endMin: next };
}

function categoryColor(category) {
  for (let i = 0; i < CATEGORIES.length; i += 1) {
    if (CATEGORIES[i].id === category) return CATEGORIES[i].color;
  }
  return null;
}

const STORAGE_KEY = "flexweek.week.v1";

const weekEl = document.getElementById("week");
const flexibleEl = document.getElementById("flexible");
const statusEl = document.getElementById("status");
const solveEl = document.getElementById("solve");
const debugEl = document.getElementById("debug");
const debugStatsEl = document.getElementById("debug-stats");
const debugUnplacedEl = document.getElementById("debug-unplaced");
const debugChangesEl = document.getElementById("debug-changes");
const debugMovesEl = document.getElementById("debug-moves");
const flexNoteEl = document.getElementById("flex-note");
const formEl = document.getElementById("block-form");
const formErrorEl = document.getElementById("form-error");
const formHeadingEl = document.getElementById("form-heading");
const formDeleteEl = document.getElementById("form-delete");
const formMissedEl = document.getElementById("form-missed");
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
  return importBlocksError(data.blocks) === null;
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
const suspendedDrafts = new Map();
let editingOccurrenceDay = null;
let editingScope = "series";
let prefs = {
  theme: "nocturne",
  reminders_enabled: false,
  reminder_lead_min: 5,
  reminder_sound: true,
};
const firedReminders = new Set();
const activeNotifications = new Set();
let reminderTimer = null;

// One record per week, keyed by its Monday. Blocks, revision, unsaved edits and
// a conflict all belong to the week they came from: a single global revision
// would let a save carry one week's blocks under another week's number.
const weeks = new Map();
let selectedWeek = currentWeekStart();
let selectedBlockId = null;
let selectedOccurrenceDay = null;
let gridGesture = null;
let savedWeeks = [];

function weekState(weekStart = selectedWeek) {
  let state = weeks.get(weekStart);
  if (!state) {
    state = { blocks: [], revision: 0, dirty: false, conflict: false, trace: null };
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
    suspendedDrafts.set(account.id, pending.map(function (weekStart) {
      const state = weekState(weekStart);
      return { weekStart: weekStart, blocks: structuredClone(state.blocks), revision: state.revision };
    }));
  }
  epoch += 1;
  account = null;
  syncReminderLoop();
  firedReminders.clear();
  activeNotifications.forEach(function (notification) {
    try { notification.close(); } catch (err) { /* ignore */ }
  });
  activeNotifications.clear();
  clearTimeout(showReminderToast._timer);
  const toast = document.getElementById("reminder-toast");
  if (toast) { toast.hidden = true; toast.textContent = ""; }
  const preferencesDialog = document.getElementById("prefs-dialog");
  if (preferencesDialog && typeof preferencesDialog.close === "function") preferencesDialog.close();
  hideContextMenu();
  if (gridGesture) clearGhost(gridGesture.lane);
  gridGesture = null;
  weeks.clear();
  savedWeeks = [];
  selectedWeek = currentWeekStart();
  saving = false;
  weekEl.replaceChildren();
  flexibleEl.replaceChildren();
  debugStatsEl.textContent = "";
  debugUnplacedEl.replaceChildren();
  debugMovesEl.replaceChildren();
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
    const data = response.status === 204 ? null : await response.json();
    if (requestEpoch !== epoch) throw new Error("Session changed. Please try again.");
    return data;
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
    savedWeeks = Array.isArray(saved.weeks) ? saved.weeks.slice() : [];
    selectedWeek = isWeekStart(week.week_start) ? week.week_start : asked;
    const state = weekState();
    state.blocks = week.blocks;
    state.revision = week.revision;
    const suspendedDraft = suspendedDrafts.get(account.id);
    if (suspendedDraft) {
      suspendedDraft.forEach(function (draft) {
        const target = weekState(draft.weekStart);
        target.blocks = draft.blocks;
        // Only the week just fetched has a known server revision to compare.
        target.conflict = draft.weekStart === selectedWeek && draft.revision !== target.revision;
        target.revision = draft.revision;
        target.dirty = true;
      });
      suspendedDrafts.delete(account.id);
    }
    applyPreferences(preferences);
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
  state.trace = null;
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
  if (!account || saving || weekStart === selectedWeek) return false;
  if (!isWeekStart(weekStart)) {
    setStatus("That is not a Monday, so it cannot open as a week.");
    return false;
  }
  const known = weeks.get(weekStart);
  // Refetching a week that holds unsaved edits would overwrite them.
  if (known && known.dirty) {
    showWeek(weekStart);
    return true;
  }
  const selectEpoch = epoch;
  saving = true;
  lockEditor(true);
  setStatus("Opening " + weekLabel(weekStart) + "…");
  try {
    const data = await api("/api/week?week_start=" + weekStart);
    if (selectEpoch !== epoch) return false;
    const opened = isWeekStart(data.week_start) ? data.week_start : weekStart;
    const state = weekState(opened);
    state.blocks = data.blocks;
    state.revision = data.revision;
    state.dirty = false;
    state.conflict = false;
    showWeek(opened);
    return true;
  } catch (error) {
    // The week did not change, so put the picker back on the one still shown.
    if (selectEpoch === epoch) { renderWeekNav(); setStatus("Could not open that week. " + error.message); }
    return false;
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

function clearSolveResult(note = "Press Solve to place these around school and sports.") {
  weekState().trace = null;
  debugEl.hidden = true;
  debugChangesEl.hidden = true;
  debugMovesEl.replaceChildren();
  flexNoteEl.textContent = note;
}

function insightFor(explanations, blockId) {
  return (explanations || []).find(function (item) {
    return item.block_id === blockId && item.slack_status;
  });
}

function occupiedIntervalsForDay(blocks, day) {
  return blocks.filter(function (block) {
    return block.start && occurrenceDays(block).indexOf(day) !== -1;
  }).map(function (block) {
    const startMin = parseStart(block.start);
    return { startMin: startMin, endMin: startMin + (block.duration_min || 0), id: block.id };
  }).sort(function (a, b) { return a.startMin - b.startMin; });
}

function selectBlock(blockId, day) {
  selectedBlockId = blockId || null;
  selectedOccurrenceDay = Number.isInteger(day) ? day : null;
  document.querySelectorAll(".block").forEach(function (el) {
    const on = selectedBlockId && el.dataset.id === selectedBlockId &&
      String(el.dataset.day) === String(selectedOccurrenceDay);
    if (on) el.classList.add("is-selected");
    else el.classList.remove("is-selected");
  });
}

function applyCreateLocked(day, startMin, endMin) {
  if (!account || saving) return null;
  const range = createDragRange(startMin, endMin);
  if (!range) return null;
  const block = {
    id: newId(),
    title: "New block",
    kind: "locked",
    duration_min: range.endMin - range.startMin,
    days: [day],
    priority: 3,
    energy: "medium",
    course: null,
    earliest: null,
    latest: null,
    start: formatMinute(range.startMin),
    missed_days: [],
    category: null,
    completed: false,
  };
  weekState().blocks.push(block);
  clearSolveResult();
  selectBlock(block.id, day);
  saveWeek();
  renderWeek();
  return block;
}

function applyCreateClick(day, startMin) {
  const occupied = occupiedIntervalsForDay(weekState().blocks, day);
  const range = createClickRange(startMin, occupied);
  if (!range) return null;
  return applyCreateLocked(day, range.startMin, range.endMin);
}

function applyBlockTimes(blockId, startMin, endMin) {
  if (!account || saving) return false;
  const block = weekState().blocks.find(function (item) { return item.id === blockId; });
  if (!block || !block.start) return false;
  // Enforced here as well as in the gesture: retiming a whole series from one
  // day's drag would change days the student never touched.
  if (block.kind === "locked" && isSeries(block)) return false;
  const dur = endMin - startMin;
  if (dur < SNAP_MIN || startMin < DAY_START_MIN || endMin > DAY_END_MIN) return false;
  block.start = formatMinute(startMin);
  block.duration_min = dur;
  clearSolveResult();
  saveWeek();
  renderWeek();
  return true;
}

function deleteBlockById(blockId) {
  if (!account || saving || !blockId) return false;
  const state = weekState();
  const before = state.blocks.length;
  state.blocks = state.blocks.filter(function (item) { return item.id !== blockId; });
  if (state.blocks.length === before) return false;
  if (selectedBlockId === blockId) selectBlock(null, null);
  closeForm();
  clearSolveResult();
  saveWeek();
  renderWeek();
  return true;
}

function hideContextMenu() {
  const menu = document.getElementById("block-context-menu");
  if (menu) menu.hidden = true;
}

function showContextMenu(clientX, clientY, blockId, day) {
  const menu = document.getElementById("block-context-menu");
  if (!menu) return;
  const source = weekState().blocks.find(function (item) { return item.id === blockId; });
  const series = source && isSeries(source) && source.kind === "locked";
  menu.querySelectorAll("button[data-action]").forEach(function (btn) {
    const action = btn.dataset.action;
    if (action === "edit") btn.hidden = Boolean(series);
    else if (action === "edit-occurrence" || action === "edit-series" || action === "delete-occurrence") {
      btn.hidden = !series;
    } else {
      btn.hidden = false;
    }
  });
  menu.hidden = false;
  menu.style.left = clientX + "px";
  menu.style.top = clientY + "px";
  menu.dataset.id = blockId;
  menu.dataset.day = String(day);
}

function yToMinute(lane, clientY) {
  const rect = lane.getBoundingClientRect();
  const hourH = hourHeightRem();
  // rem → px via the same computed --hour-h used for layout
  const hourPx = rect.height / ((DAY_END_MIN - DAY_START_MIN) / 60);
  const y = clientY - rect.top;
  return DAY_START_MIN + (y / hourPx) * 60;
}

function editModeForBlock(el, clientY) {
  const rect = el.getBoundingClientRect();
  if (rect.height >= 2 * EDGE_PX + 6) {
    if (clientY - rect.top <= EDGE_PX) return "resize_top";
    if (rect.bottom - clientY <= EDGE_PX) return "resize_bottom";
  }
  return "move";
}

function ensureGhost(lane) {
  let ghost = lane.querySelector(".drag-ghost");
  if (!ghost) {
    ghost = document.createElement("div");
    ghost.className = "drag-ghost";
    lane.appendChild(ghost);
  }
  return ghost;
}

function placeGhost(lane, startMin, endMin) {
  const ghost = ensureGhost(lane);
  const hourH = hourHeightRem();
  ghost.hidden = false;
  ghost.style.top = ((startMin - DAY_START_MIN) / 60) * hourH + "rem";
  ghost.style.height = Math.max(((endMin - startMin) / 60) * hourH, 0.4) + "rem";
}

function clearGhost(lane) {
  const ghost = lane && lane.querySelector(".drag-ghost");
  if (ghost) ghost.hidden = true;
}

function bindDayLane(lane, day) {
  lane.addEventListener("pointerdown", function (event) {
    if (!account || saving || gridGesture || event.button !== 0) return;
    hideContextMenu();
    const blockEl = event.target.closest ? event.target.closest(".block") : null;
    const pressMin = yToMinute(lane, event.clientY);
    if (blockEl && lane.contains(blockEl)) {
      const blockId = blockEl.dataset.id;
      const source = weekState().blocks.find(function (item) { return item.id === blockId; });
      if (!source || !source.start) return;
      // Dragging one day of a repeating block is ambiguous: it could move that
      // occurrence or the whole series. The app already asks that question
      // everywhere else, so refuse the gesture rather than silently pick one.
      if (source.kind === "locked" && isSeries(source)) {
        selectBlock(blockId, day);
        setStatus(
          source.title + " repeats on " + source.days.length +
          " days, so dragging it is ambiguous. Right-click for Edit occurrence or Edit series."
        );
        return;
      }
      const startMin = parseStart(source.start);
      const endMin = startMin + (source.duration_min || 0);
      const mode = editModeForBlock(blockEl, event.clientY);
      selectBlock(blockId, day);
      gridGesture = {
        type: mode,
        day: day,
        lane: lane,
        blockId: blockId,
        originStart: startMin,
        originEnd: endMin,
        pressMin: pressMin,
        moved: false,
        pointerId: event.pointerId,
      };
      try { lane.setPointerCapture(event.pointerId); } catch (err) { /* harness */ }
      event.preventDefault();
      return;
    }
    selectBlock(null, null);
    gridGesture = {
      type: "create",
      day: day,
      lane: lane,
      startMin: snapMinute(pressMin),
      curMin: snapMinute(pressMin),
      moved: false,
      pointerId: event.pointerId,
    };
    placeGhost(lane, gridGesture.startMin, Math.min(gridGesture.startMin + SNAP_MIN, DAY_END_MIN));
    try { lane.setPointerCapture(event.pointerId); } catch (err) { /* harness */ }
    event.preventDefault();
  });

  lane.addEventListener("pointermove", function (event) {
    if (!gridGesture || gridGesture.lane !== lane || gridGesture.pointerId !== event.pointerId) return;
    const cur = yToMinute(lane, event.clientY);
    if (gridGesture.type === "create") {
      gridGesture.curMin = snapMinute(cur);
      if (Math.abs(gridGesture.curMin - gridGesture.startMin) >= SNAP_MIN) gridGesture.moved = true;
      const range = createDragRange(gridGesture.startMin, gridGesture.curMin);
      if (range) placeGhost(lane, range.startMin, range.endMin);
      return;
    }
    const delta = cur - gridGesture.pressMin;
    let range;
    if (gridGesture.type === "move") range = moveRange(gridGesture.originStart, gridGesture.originEnd, delta);
    else if (gridGesture.type === "resize_top") range = resizeTopRange(gridGesture.originStart, gridGesture.originEnd, delta);
    else range = resizeBottomRange(gridGesture.originStart, gridGesture.originEnd, delta);
    if (range.startMin !== gridGesture.originStart || range.endMin !== gridGesture.originEnd) gridGesture.moved = true;
    placeGhost(lane, range.startMin, range.endMin);
    gridGesture.preview = range;
  });

  function finishGesture(event) {
    if (!gridGesture || gridGesture.lane !== lane || gridGesture.pointerId !== event.pointerId) return;
    const gesture = gridGesture;
    gridGesture = null;
    clearGhost(lane);
    try { lane.releasePointerCapture(gesture.pointerId); } catch (err) { /* harness */ }
    if (event.type === "pointercancel") return;
    if (gesture.type === "create") {
      if (gesture.moved) {
        const range = createDragRange(gesture.startMin, gesture.curMin);
        if (range) applyCreateLocked(gesture.day, range.startMin, range.endMin);
      } else {
        applyCreateClick(gesture.day, gesture.startMin);
      }
      return;
    }
    if (gesture.moved && gesture.preview) {
      applyBlockTimes(gesture.blockId, gesture.preview.startMin, gesture.preview.endMin);
      selectBlock(gesture.blockId, gesture.day);
      return;
    }
    selectBlock(gesture.blockId, gesture.day);
  }

  lane.addEventListener("pointerup", finishGesture);
  lane.addEventListener("pointercancel", finishGesture);

  lane.addEventListener("dblclick", function (event) {
    const blockEl = event.target.closest ? event.target.closest(".block") : null;
    if (!blockEl || !lane.contains(blockEl)) return;
    event.preventDefault();
    gridGesture = null;
    clearGhost(lane);
    const source = weekState().blocks.find(function (item) { return item.id === blockEl.dataset.id; });
    if (source) {
      selectBlock(source.id, day);
      openForm(source.kind, source, day);
    }
  });

  lane.addEventListener("contextmenu", function (event) {
    const blockEl = event.target.closest ? event.target.closest(".block") : null;
    if (!blockEl || !lane.contains(blockEl)) return;
    event.preventDefault();
    const blockId = blockEl.dataset.id;
    selectBlock(blockId, day);
    showContextMenu(event.clientX, event.clientY, blockId, day);
  });
}

function buildGrid(blocks, explanations = []) {
  weekEl.innerHTML = "";
  hideContextMenu();
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
  const gutter = document.createElement("div");
  gutter.className = "hours";
  hours.forEach((hour) => {
    const label = document.createElement("div");
    label.className = "hour";
    label.textContent = pad(hour) + ":00";
    gutter.appendChild(label);
  });
  weekEl.appendChild(gutter);

  const lanes = [];
  for (let day = 0; day < 7; day += 1) {
    const lane = document.createElement("div");
    lane.className = "day-lane";
    lane.dataset.day = String(day);
    lane.style.height = (hours.length * hourH) + "rem";
    weekEl.appendChild(lane);
    lanes.push(lane);
    bindDayLane(lane, day);
  }

  const visibleEnd = END_HOUR * 60;
  const visibleStart = START_HOUR * 60;

  blocks.filter((b) => b.start).forEach((block) => {
    const renderedDays = occurrenceDays(block);
    renderedDays.forEach((day) => {
      const startMin = parseStart(block.start);
      const endMin = Math.min(visibleEnd, startMin + (block.duration_min || 0));
      const clippedStart = Math.max(visibleStart, startMin);
      if (endMin <= clippedStart) return;
      if (day < 0 || day > 6) return;

      const el = document.createElement("div");
      const missed = block.kind === "locked" && (block.missed_days || []).indexOf(day) !== -1;
      el.className = "block" + (block.kind === "flexible" ? " flex-block" : "") +
        (missed ? " missed-block" : "") + (block.completed ? " is-completed" : "");
      el.dataset.id = block.id;
      el.dataset.day = String(day);
      el.style.top = ((clippedStart - visibleStart) / 60) * hourH + "rem";
      el.style.height = Math.max(((endMin - clippedStart) / 60) * hourH, 1.1) + "rem";
      const color = categoryColor(block.category);
      if (color) {
        el.style.borderLeftColor = color;
        el.style.borderLeftWidth = "4px";
      }
      el.title = block.title + (block.course ? " · " + block.course : "") +
        (missed ? " · missed" : "") + " (double-click to edit)";

      const title = document.createElement("div");
      title.className = "title";
      title.textContent = block.title;
      el.appendChild(title);

      const sub = document.createElement("div");
      sub.className = "sub";
      sub.textContent = block.duration_min + " min" + (missed ? " · missed" : "");
      el.appendChild(sub);

      const insight = insightFor(explanations, block.id);
      if (insight) {
        const slack = document.createElement("span");
        slack.className = "slack-badge slack-" + insight.slack_status;
        slack.textContent = insight.slack_status + " slack";
        slack.title = insight.message;
        el.appendChild(slack);
      }

      if (selectedBlockId === block.id && selectedOccurrenceDay === day) {
        el.classList.add("is-selected");
      }

      lanes[day].appendChild(el);
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
    li.className = "task-card" + (block.completed ? " is-completed" : "");
    li.dataset.id = block.id;
    const color = categoryColor(block.category);
    if (color) li.style.borderLeftColor = color;
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
    if (block.category) pill(categoryLabel(block.category) || block.category);
    if (block.latest) pill("due " + block.latest);
    if (block.completed) pill("done");

    li.appendChild(pills);
    li.addEventListener("click", function () {
      const source = weekState().blocks.find(function (item) { return item.id === block.id; });
      if (source) openForm(source.kind, source);
    });
    flexibleEl.appendChild(li);
  });
}

function formatPlacement(day, start) {
  if (day === null || day === undefined || !start) return "unplaced";
  return DAYS[day] + " " + start;
}

function blockTitle(blockId) {
  const block = weekState().blocks.find(function (item) { return item.id === blockId; });
  return block ? block.title : blockId;
}

function highlightBlock(blockId) {
  let target = null;
  document.querySelectorAll(".block, .task-card").forEach(function (element) {
    element.classList.remove("is-highlighted");
    if (!target && element.dataset.id === blockId) target = element;
  });
  if (target) {
    target.classList.add("is-highlighted");
    if (typeof target.scrollIntoView === "function") target.scrollIntoView({ block: "nearest" });
  }
}

function detailButton(text, blockId, day = null) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "detail-button";
  button.textContent = text;
  button.dataset.id = blockId;
  button.addEventListener("click", function () {
    if (day === null) {
      highlightBlock(blockId);
      return;
    }
    const source = weekState().blocks.find(function (item) { return item.id === blockId; });
    if (source) openForm(source.kind, source, day);
  });
  return button;
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
  (trace.explanations || []).forEach((item) => {
    const li = document.createElement("li");
    li.appendChild(detailButton(blockTitle(item.block_id) + " — " + item.message, item.block_id));
    debugUnplacedEl.appendChild(li);
  });
  if (!(trace.explanations || []).length) {
    const li = document.createElement("li");
    li.textContent = "All tasks fit their requested windows.";
    debugUnplacedEl.appendChild(li);
  }

  debugMovesEl.innerHTML = "";
  const missedOccurrences = [];
  weekState().blocks.filter(function (block) { return block.kind === "locked"; }).forEach(function (block) {
    (block.missed_days || []).forEach(function (day) {
      missedOccurrences.push({ blockId: block.id, day: day });
    });
  });
  const changedMoves = (trace.moves || []).filter(function (move) {
    return move.from_day !== null || move.to_day !== null;
  });
  debugChangesEl.hidden = !missedOccurrences.length && !changedMoves.length;
  missedOccurrences.forEach(function (missed) {
    const li = document.createElement("li");
    li.appendChild(detailButton(
      DAYS[missed.day] + " " + blockTitle(missed.blockId) + " marked missed. Click to open restore.",
      missed.blockId,
      missed.day,
    ));
    debugMovesEl.appendChild(li);
  });
  changedMoves.forEach(function (move) {
    const li = document.createElement("li");
    li.appendChild(detailButton(
      blockTitle(move.block_id) + " · " +
        formatPlacement(move.from_day, move.from_start) + " → " +
        formatPlacement(move.to_day, move.to_start),
      move.block_id,
    ));
    debugMovesEl.appendChild(li);
  });
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

function ensureCategoryOptions() {
  const select = document.getElementById("f-category");
  if (!select) return;
  if (select.dataset.ready !== "1") {
    select.innerHTML = "";
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "None";
    select.appendChild(blank);
    CATEGORIES.forEach(function (cat) {
      const opt = document.createElement("option");
      opt.value = cat.id;
      opt.textContent = cat.label;
      select.appendChild(opt);
    });
    select.dataset.ready = "1";
  }
  renderCategoryChips(document.getElementById("category-chips"), select.value || "", true);
  renderCategoryChips(document.getElementById("category-legend"), "", false);
}

function renderCategoryChips(container, selected, interactive) {
  if (!container) return;
  container.innerHTML = "";
  if (interactive) {
    const none = document.createElement("button");
    none.type = "button";
    none.className = "category-chip" + (!selected ? " is-selected" : "");
    none.textContent = "None";
    none.addEventListener("click", function () {
      document.getElementById("f-category").value = "";
      renderCategoryChips(container, "", true);
    });
    container.appendChild(none);
  }
  CATEGORIES.forEach(function (cat) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "category-chip" + (selected === cat.id ? " is-selected" : "");
    if (btn.style && typeof btn.style.setProperty === "function") {
      btn.style.setProperty("--chip-color", cat.color);
    } else if (btn.style) {
      btn.style.borderLeftColor = cat.color;
    }
    btn.textContent = cat.label;
    btn.dataset.category = cat.id;
    if (interactive) {
      btn.addEventListener("click", function () {
        document.getElementById("f-category").value = cat.id;
        renderCategoryChips(container, cat.id, true);
      });
    } else {
      btn.disabled = true;
    }
    container.appendChild(btn);
  });
}

function selectedEditScope() {
  const checked = formEl.querySelector('input[name="f-scope"]:checked');
  return checked ? checked.value : "series";
}

function setEditScope(scope) {
  editingScope = scope === "occurrence" ? "occurrence" : "series";
  formEl.querySelectorAll('input[name="f-scope"]').forEach(function (el) {
    el.checked = el.value === editingScope;
  });
  const daysField = formEl.querySelector("fieldset.days");
  if (daysField) {
    const lockDays = editingScope === "occurrence" && editingOccurrenceDay !== null;
    daysField.querySelectorAll('input[name="f-day"]').forEach(function (el) {
      el.disabled = lockDays;
      if (lockDays) el.checked = Number(el.value) === editingOccurrenceDay;
    });
  }
}

function applyPreferences(preferences) {
  prefs = {
    theme: preferences.theme || "nocturne",
    reminders_enabled: Boolean(preferences.reminders_enabled),
    reminder_lead_min: Number.isFinite(Number(preferences.reminder_lead_min))
      ? Number(preferences.reminder_lead_min) : 5,
    reminder_sound: preferences.reminder_sound !== false,
  };
  themeEl.value = prefs.theme;
  document.documentElement.dataset.theme = prefs.theme;
  const enabled = document.getElementById("pref-reminders-enabled");
  const lead = document.getElementById("pref-reminder-lead");
  const sound = document.getElementById("pref-reminder-sound");
  if (enabled) enabled.checked = prefs.reminders_enabled;
  if (lead) lead.value = String(prefs.reminder_lead_min);
  if (sound) sound.checked = prefs.reminder_sound;
  syncReminderLoop();
}

function preferencesPayload() {
  return {
    theme: themeEl.value,
    reminders_enabled: prefs.reminders_enabled,
    reminder_lead_min: prefs.reminder_lead_min,
    reminder_sound: prefs.reminder_sound,
  };
}

function toggleCompleted(blockId) {
  if (!account || saving || !blockId) return false;
  const block = weekState().blocks.find(function (item) { return item.id === blockId; });
  if (!block) return false;
  block.completed = !block.completed;
  if (block.completed && block.kind === "flexible") {
    const placed = weekState().trace?.placed.find(item => item.id === blockId);
    if (placed && placed.start && placed.days.length === 1) {
      block.start = placed.start;
      block.completed_day = placed.days[0];
    } else if (!Number.isInteger(block.completed_day)) {
      block.start = null;
    }
  } else if (block.kind === "flexible") {
    block.start = null;
    delete block.completed_day;
  }
  clearSolveResult();
  saveWeek();
  renderWeek();
  return true;
}

function deleteOccurrenceById(blockId, day) {
  if (!account || saving || !blockId || !Number.isInteger(day)) return false;
  const state = weekState();
  const index = state.blocks.findIndex(function (item) { return item.id === blockId; });
  if (index < 0) return false;
  const updated = removeOccurrence(state.blocks[index], day);
  if (updated) state.blocks[index] = updated;
  else state.blocks.splice(index, 1);
  if (selectedBlockId === blockId) selectBlock(null, null);
  closeForm();
  clearSolveResult();
  saveWeek();
  renderWeek();
  return true;
}

function downloadText(filename, body, mime) {
  const url = URL.createObjectURL(new Blob([body], { type: mime || "text/plain" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
}

function exportCurrentWeek(asText) {
  if (!account) return;
  const state = weekState();
  const blocks = state.blocks;
  if (asText) {
    downloadText("flexweek-" + selectedWeek + ".txt",
      formatWeekExportText(selectedWeek, presentationBlocks(state)), "text/plain");
    return;
  }
  downloadText(
    "flexweek-" + selectedWeek + ".json",
    JSON.stringify(exportWeekPayload(selectedWeek, blocks), null, 2),
    "application/json",
  );
}

function exportDay(day, asText) {
  if (!account || !Number.isInteger(day)) return;
  const payload = exportDayPayload(selectedWeek, day, presentationBlocks(weekState()));
  if (asText) {
    const lines = ["FlexWeek day — " + DAYS[day] + " " + (payload.date || ""), ""];
    payload.blocks.forEach(function (block) {
      if (!block.start) {
        lines.push(block.title + " (unplaced, " + block.duration_min + " min)");
        return;
      }
      lines.push(block.start + "  " + block.title + (block.completed ? " [done]" : ""));
    });
    downloadText("flexweek-day-" + (payload.date || day) + ".txt", lines.join("\n") + "\n", "text/plain");
    return;
  }
  downloadText(
    "flexweek-day-" + (payload.date || day) + ".json",
    JSON.stringify(payload, null, 2),
    "application/json",
  );
}

async function importPayloadIntoWeek(parsed, mode) {
  if (!account || saving) return false;
  if (!parsed || parsed.error) {
    setStatus(parsed && parsed.error ? parsed.error : "Import failed.");
    return false;
  }
  const targetWeek = parsed.week_start && isWeekStart(parsed.week_start) ? parsed.week_start : selectedWeek;
  if (targetWeek !== selectedWeek) {
    const ok = confirm(
      "This file is for " + weekLabel(targetWeek) + ". Open that week and import without changing other weeks?"
    );
    if (!ok) return false;
    // If the switch fails, the week on screen is unchanged; importing there
    // would overwrite the wrong week, so abort before touching any blocks.
    const opened = await selectWeek(targetWeek);
    if (!opened || selectedWeek !== targetWeek) {
      setStatus("Could not open " + weekLabel(targetWeek) + ". Import cancelled.");
      return false;
    }
  }
  const state = weekState();
  const mergeMode = mode || (parsed.format === "flexweek-day" ? "merge" : "replace");
  if (mergeMode === "replace" && state.blocks.length) {
    if (!confirm("Replace blocks in " + weekLabel(selectedWeek) + " with the import? Other weeks stay untouched.")) {
      return false;
    }
  }
  let merged;
  try { merged = mergeImportedBlocks(state.blocks, parsed.blocks, mergeMode, parsed.day); }
  catch (error) { setStatus(error.message + " Nothing was imported."); return false; }
  const problem = importBlocksError(merged);
  if (problem) { setStatus(problem + " Nothing was imported."); return false; }
  state.blocks = merged;
  closeForm();
  clearSolveResult();
  renderWeek();
  return saveWeek();
}

function showReminderToast(message) {
  const toast = document.getElementById("reminder-toast");
  if (!toast) return;
  toast.hidden = false;
  toast.textContent = message;
  clearTimeout(showReminderToast._timer);
  showReminderToast._timer = setTimeout(function () { toast.hidden = true; }, 8000);
}

function playReminderSound() {
  if (!prefs.reminder_sound) return;
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = playReminderSound._ctx || new Ctx();
    playReminderSound._ctx = ctx;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.value = 0.04;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.18);
  } catch (err) { /* best-effort */ }
}

function maybeNotify(title, body) {
  showReminderToast(title + (body ? " — " + body : ""));
  playReminderSound();
  if (typeof Notification !== "function") return;
  if (Notification.permission === "granted") {
    try {
      const notification = new Notification(title, { body: body || "", silent: true });
      activeNotifications.add(notification);
      const remove = function () { activeNotifications.delete(notification); };
      notification.onclose = remove;
      notification.onerror = remove;
    } catch (err) { /* ignore */ }
    return;
  }
  if (Notification.permission === "default") {
    Notification.requestPermission().catch(function () {});
  }
}

function checkReminders(nowDate) {
  if (!account || !prefs.reminders_enabled) return;
  const now = nowDate || new Date();
  const todayIso = now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
  const nowMin = now.getHours() * 60 + now.getMinutes();
  const lead = prefs.reminder_lead_min;
  const reminderWeek = mondayOf(todayIso);
  const state = weeks.get(reminderWeek);
  if (!state) return;
  const sources = new Map(state.blocks.map(function (block) { return [block.id, block]; }));
  const reminderBlocks = state.trace ? state.blocks.filter(function (block) {
    return block.kind === "locked";
  }).concat((state.trace.placed || []).filter(function (block) {
    return block.kind === "flexible";
  }).map(function (placed) {
    const source = sources.get(placed.id);
    return source ? { ...placed, completed: source.completed,
      missed_days: source.missed_days || [] } : placed;
  })) : state.blocks;
  reminderBlocks.forEach(function (block) {
    if (!block.start || block.completed) return;
    occurrenceDays(block).forEach(function (day) {
      if ((block.missed_days || []).indexOf(day) !== -1) return;
      const date = dateForDay(reminderWeek, day);
      if (date !== todayIso) return;
      const startMin = parseStart(block.start);
      if (!startAlertDue(startMin, nowMin, lead, REMINDER_WINDOW_MIN)) return;
      const key = reminderKey(reminderWeek, block.id, day, block.start);
      if (firedReminders.has(key)) return;
      firedReminders.add(key);
      maybeNotify(block.title + " starts soon", block.start + " · " + DAYS[day]);
    });
  });
}

function syncReminderLoop() {
  if (reminderTimer) {
    clearInterval(reminderTimer);
    reminderTimer = null;
  }
  if (!account || !prefs.reminders_enabled) return;
  checkReminders();
  reminderTimer = setInterval(function () { checkReminders(); }, REMINDER_POLL_MS);
  if (reminderTimer && typeof reminderTimer.unref === "function") reminderTimer.unref();
}

function openForm(kind, block, occurrenceDay = null, scope = null) {
  if (!account || saving) return;
  const editing = Boolean(block);
  editingOccurrenceDay = Number.isInteger(occurrenceDay) ? occurrenceDay : null;
  formEl.hidden = false;
  showFormError("");
  document.getElementById("f-kind").value = kind;
  document.getElementById("f-id").value = editing ? block.id : "";
  formHeadingEl.textContent = (editing ? "Edit " : "Add ") + (kind === "locked" ? "locked" : "task");
  formDeleteEl.hidden = !editing;
  const canChangeMissed = editing && kind === "locked" && editingOccurrenceDay !== null;
  formMissedEl.hidden = !canChangeMissed || (!(block.missed_days || []).includes(editingOccurrenceDay) && !weekState().trace);
  if (canChangeMissed) {
    const isMissed = (block.missed_days || []).includes(editingOccurrenceDay);
    formMissedEl.textContent = isMissed ? "Restore " + DAYS[editingOccurrenceDay] : "Mark " + DAYS[editingOccurrenceDay] + " missed";
    formMissedEl.className = isMissed ? "secondary" : "danger";
  }
  lockedFieldsEl.hidden = kind !== "locked";
  flexFieldsEl.hidden = kind !== "flexible";

  const scopeEl = document.getElementById("edit-scope");
  const showScope = editing && kind === "locked" && isSeries(block) && editingOccurrenceDay !== null;
  if (scopeEl) scopeEl.hidden = !showScope;
  if (showScope) {
    setEditScope(scope === "series" ? "series" : "occurrence");
  } else {
    setEditScope("series");
    formEl.querySelectorAll('input[name="f-day"]').forEach(function (el) { el.disabled = false; });
  }

  ensureCategoryOptions();
  document.getElementById("f-title").value = editing ? block.title : "";
  document.getElementById("f-course").value = editing && block.course ? block.course : "";
  document.getElementById("f-category").value = editing && block.category ? block.category : "";
  document.getElementById("f-completed").checked = Boolean(editing && block.completed);
  document.getElementById("f-duration").value = editing ? String(block.duration_min) : "60";
  setSelectedDays(editing ? (showScope && editingScope === "occurrence" ? [editingOccurrenceDay] : block.days) : []);
  startEl.value = editing && block.start ? block.start : "16:00";
  document.getElementById("f-priority").value = editing && block.priority ? String(block.priority) : "3";
  document.getElementById("f-energy").value = editing && block.energy ? block.energy : "medium";
  const latest = parseLatest(editing ? block.latest : "");
  document.getElementById("f-due-day").value = latest.day;
  dueTimeEl.value = latest.time || "21:00";
  renderCategoryChips(document.getElementById("category-chips"), document.getElementById("f-category").value || "", true);
  if (showScope) setEditScope(editingScope);
  formDeleteEl.textContent = showScope && editingScope === "occurrence" ? "Remove this day" : "Delete";
  document.getElementById("f-title").focus();
}

function closeForm() {
  formEl.hidden = true;
  editingOccurrenceDay = null;
  editingScope = "series";
  formEl.querySelectorAll('input[name="f-day"]').forEach(function (el) { el.disabled = false; });
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
  const scope = selectedEditScope();
  const days = (scope === "occurrence" && editingOccurrenceDay !== null)
    ? [editingOccurrenceDay]
    : selectedDays();
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
  const prior = existing >= 0 ? blocks[existing] : null;
  const patch = {
    title: title,
    duration_min: Number(document.getElementById("f-duration").value),
    days: days,
    priority: Number(document.getElementById("f-priority").value) || 3,
    energy: document.getElementById("f-energy").value || "medium",
    course: document.getElementById("f-course").value.trim() || null,
    category: document.getElementById("f-category").value || null,
    completed: document.getElementById("f-completed").checked,
    earliest: null,
    latest: null,
    start: kind === "locked" ? startEl.value : null,
  };
  if (kind === "flexible") {
    const dueDay = document.getElementById("f-due-day").value;
    const dueTime = dueTimeEl.value;
    if (dueDay !== "" && dueTime) {
      patch.latest = DAY_FULL[Number(dueDay)] + " " + dueTime;
    }
    if (patch.completed && prior) {
      const placed = weekState().trace?.placed.find(item => item.id === id) || prior;
      const completedDay = Number.isInteger(placed.completed_day)
        ? placed.completed_day
        : (placed.days.length === 1 ? placed.days[0] : null);
      if (placed.start && completedDay !== null && days.includes(completedDay)) {
        patch.start = placed.start;
        patch.completed_day = completedDay;
      }
    } else {
      patch.start = null;
      patch.completed_day = null;
    }
  }

  if (prior && kind === "locked" && isSeries(prior) && scope === "occurrence" && editingOccurrenceDay !== null) {
    const result = editOccurrence(prior, editingOccurrenceDay, {
      title: patch.title,
      duration_min: patch.duration_min,
      priority: patch.priority,
      energy: patch.energy,
      course: patch.course,
      category: patch.category,
      completed: patch.completed,
      start: patch.start,
      earliest: null,
      latest: null,
    });
    if (result.series) blocks[existing] = result.series;
    else blocks.splice(existing, 1);
    if (result.split) blocks.push(result.split);
  } else {
    const block = {
      id: id,
      kind: kind,
      missed_days: kind === "locked" && prior ? (prior.missed_days || []).filter(function (day) {
        return days.includes(day);
      }) : [],
      ...patch,
    };
    if (existing >= 0) blocks[existing] = block;
    else blocks.push(block);
  }

  closeForm();
  clearSolveResult();
  saveWeek();
  renderWeek();
});

document.getElementById("form-cancel").addEventListener("click", closeForm);

formMissedEl.addEventListener("click", async function () {
  if (!account || saving || editingOccurrenceDay === null) return;
  const id = document.getElementById("f-id").value;
  const block = weekState().blocks.find(function (item) { return item.id === id; });
  if (!block || block.kind !== "locked") return;
  const isMissed = (block.missed_days || []).includes(editingOccurrenceDay);
  if (!isMissed) {
    await recoverMissedOccurrence(id, editingOccurrenceDay);
    return;
  }
  block.missed_days = block.missed_days.filter(function (day) { return day !== editingOccurrenceDay; });
  closeForm();
  clearSolveResult();
  renderWeek();
  await saveWeek();
});

formDeleteEl.addEventListener("click", function () {
  if (!account || saving) return;
  const id = document.getElementById("f-id").value;
  const prior = weekState().blocks.find(function (item) { return item.id === id; });
  if (prior && isSeries(prior) && selectedEditScope() === "occurrence" && editingOccurrenceDay !== null) {
    deleteOccurrenceById(id, editingOccurrenceDay);
    return;
  }
  deleteBlockById(id);
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
  clearSolveResult("Add locked school or sports, then homework as tasks.");
  saveWeek();
  renderWeek();
});

function missedHistoryBlocks() {
  return weekState().blocks.filter(function (block) {
    return block.kind === "locked" && (block.missed_days || []).length;
  }).map(function (block) {
    return { ...block, days: block.missed_days.slice() };
  });
}

function showTrace(trace) {
  weekState().trace = trace;
  buildGrid((trace.placed || []).concat(missedHistoryBlocks()), trace.explanations || []);
  renderFlexible(trace.unplaced || []);
  renderDebug(trace);
  flexNoteEl.textContent = trace.unplaced.length ?
    "Some tasks could not be placed. Select a reason below to find the task." :
    "All flexible tasks are on the grid.";
  setStatus((weekState().dirty ? "Unsaved week · " : "Saved week · ") +
    trace.placed.filter(b => b.kind === "flexible").length + " tasks placed");
}

async function solveWeek() {
  if (!account || saving) return;
  const solveEpoch = epoch;
  saving = true;
  lockEditor(true);
  setStatus("Solving…");
  try {
    const trace = await api("/api/solve", { method: "POST", body: JSON.stringify({ blocks: weekState().blocks }) });
    if (solveEpoch !== epoch) return;
    showTrace(trace);
  } catch (error) {
    if (solveEpoch === epoch) setStatus("Solve failed. " + error.message);
  } finally {
    if (solveEpoch === epoch) { saving = false; lockEditor(false); }
  }
}

async function recoverMissedOccurrence(blockId, day) {
  const state = weekState();
  if (!account || saving || !state.trace) return;
  const recoverEpoch = epoch;
  const previous = state.trace.placed || [];
  let recovered = false;
  saving = true;
  lockEditor(true);
  setStatus("Replanning after the miss…");
  try {
    const trace = await api("/api/solve", { method: "POST", body: JSON.stringify({
      blocks: state.blocks,
      recover: { missed_block_id: blockId, missed_day: day, previous_placed: previous },
    }) });
    if (recoverEpoch !== epoch) return;
    const block = state.blocks.find(function (item) { return item.id === blockId; });
    if (!block) return;
    block.missed_days = Array.from(new Set([...(block.missed_days || []), day])).sort();
    state.dirty = true;
    closeForm();
    showTrace(trace);
    recovered = true;
  } catch (error) {
    if (recoverEpoch === epoch) setStatus("Could not replan. " + error.message);
  } finally {
    if (recoverEpoch === epoch) { saving = false; lockEditor(false); }
  }
  if (recovered && recoverEpoch === epoch) await saveWeek();
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
    if (account) suspendedDrafts.delete(account.id);
    signedOut("Signed out.", false);
    channel?.postMessage("session-changed");
  } catch (error) { if (logoutEpoch === epoch) setStatus("Sign out failed. " + error.message); }
});

if (channel) channel.onmessage = () => signedOut("The account session changed in another window. Sign in to continue.");

themeEl.addEventListener("change", async () => {
  const oldTheme = document.documentElement.dataset.theme;
  const themeEpoch = epoch;
  document.documentElement.dataset.theme = themeEl.value;
  prefs.theme = themeEl.value;
  themeEl.disabled = true;
  try { await api("/api/preferences", { method: "PUT", body: JSON.stringify(preferencesPayload()) }); }
  catch (error) {
    if (themeEpoch === epoch) {
      themeEl.value = oldTheme;
      prefs.theme = oldTheme;
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
    clearSolveResult();
    renderWeek();
    setStatus("Reloaded saved week.");
  } catch (error) { if (reloadEpoch === epoch) setStatus(error.message); }
  finally { if (reloadEpoch === epoch) { saving = false; lockEditor(false); } }
});
document.getElementById("download-draft").addEventListener("click", () => {
  if (!account) return;
  const draft = exportWeekPayload(selectedWeek, weekState().blocks);
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
  clearSolveResult();
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
const contextMenuEl = document.getElementById("block-context-menu");
if (contextMenuEl) {
  contextMenuEl.addEventListener("click", function (event) {
    const button = event.target.closest ? event.target.closest("button[data-action]") : null;
    if (!button) return;
    const blockId = contextMenuEl.dataset.id;
    const day = Number(contextMenuEl.dataset.day);
    hideContextMenu();
    const source = weekState().blocks.find(function (item) { return item.id === blockId; });
    const action = button.dataset.action;
    if (action === "edit" || action === "edit-occurrence") {
      if (source) openForm(source.kind, source, Number.isInteger(day) ? day : null, "occurrence");
      return;
    }
    if (action === "edit-series") {
      if (source) openForm(source.kind, source, Number.isInteger(day) ? day : null, "series");
      return;
    }
    if (action === "delete-occurrence") {
      deleteOccurrenceById(blockId, day);
      return;
    }
    if (action === "toggle-completed") {
      toggleCompleted(blockId);
      return;
    }
    if (action === "export-day") {
      exportDay(day, false);
      return;
    }
    if (action === "delete") deleteBlockById(blockId);
  });
}
document.addEventListener("pointerdown", function (event) {
  const menu = document.getElementById("block-context-menu");
  if (!menu || menu.hidden) return;
  if (menu.contains(event.target)) return;
  hideContextMenu();
});

solveEl.addEventListener("click", solveWeek);
document.getElementById("week-prev").addEventListener("click", () => selectWeek(shiftWeek(selectedWeek, -1)));
document.getElementById("week-next").addEventListener("click", () => selectWeek(shiftWeek(selectedWeek, 1)));
document.getElementById("week-today").addEventListener("click", () => selectWeek(currentWeekStart()));
weekJumpEl.addEventListener("change", () => selectWeek(weekJumpEl.value));

const prefsOpen = document.getElementById("prefs-open");
const prefsDialog = document.getElementById("prefs-dialog");
const prefsForm = document.getElementById("prefs-form");
if (prefsOpen && prefsDialog) {
  prefsOpen.addEventListener("click", function () {
    applyPreferences(prefs);
    if (typeof prefsDialog.showModal === "function") prefsDialog.showModal();
    else prefsDialog.setAttribute("open", "open");
  });
}
if (prefsForm) {
  prefsForm.addEventListener("submit", async function (event) {
    const submitter = event.submitter;
    const value = submitter ? submitter.value : "cancel";
    if (value !== "save") return;
    event.preventDefault();
    if (!account) return;
    const preferenceEpoch = epoch;
    const enabledEl = document.getElementById("pref-reminders-enabled");
    const leadEl = document.getElementById("pref-reminder-lead");
    const soundEl = document.getElementById("pref-reminder-sound");
    const next = {
      theme: themeEl.value,
      reminders_enabled: Boolean(enabledEl && enabledEl.checked),
      reminder_lead_min: Math.max(0, Math.min(120, Number(leadEl && leadEl.value) || 0)),
      reminder_sound: Boolean(soundEl && soundEl.checked),
    };
    const err = document.getElementById("prefs-error");
    try {
      const saved = await api("/api/preferences", { method: "PUT", body: JSON.stringify(next) });
      if (preferenceEpoch !== epoch) return;
      applyPreferences(saved);
      if (err) { err.hidden = true; err.textContent = ""; }
      if (prefsDialog && typeof prefsDialog.close === "function") prefsDialog.close();
      else if (prefsDialog) prefsDialog.removeAttribute("open");
      setStatus(next.reminders_enabled ? "Reminders on · " + next.reminder_lead_min + " min lead." : "Reminders off.");
      if (next.reminders_enabled && typeof Notification === "function" && Notification.permission === "default") {
        Notification.requestPermission().catch(function () {});
      }
    } catch (error) {
      if (preferenceEpoch !== epoch) return;
      if (err) { err.hidden = false; err.textContent = error.message; }
      else setStatus("Reminders were not saved. " + error.message);
    }
  });
}

const exportWeekBtn = document.getElementById("export-week");
if (exportWeekBtn) {
  exportWeekBtn.addEventListener("click", function (event) {
    const asText = Boolean(event && event.shiftKey);
    exportCurrentWeek(asText);
    setStatus(asText ? "Exported week as text." : "Exported week as JSON. Shift-click for text.");
  });
}
const importFileBtn = document.getElementById("import-file");
const importFileInput = document.getElementById("import-file-input");
if (importFileBtn && importFileInput) {
  importFileBtn.addEventListener("click", function () { importFileInput.click(); });
  importFileInput.addEventListener("change", async function () {
    if (!account || saving) return;
    const importEpoch = epoch;
    const importWeek = selectedWeek;
    const file = importFileInput.files && importFileInput.files[0];
    importFileInput.value = "";
    if (!file) return;
    try {
      const text = await file.text();
      if (importEpoch !== epoch || importWeek !== selectedWeek) return;
      const parsed = parseImportPayload(text);
      const ok = await importPayloadIntoWeek(parsed);
      if (ok) setStatus("Imported into " + weekLabel(selectedWeek) + ".");
    } catch (error) {
      if (importEpoch !== epoch || importWeek !== selectedWeek) return;
      setStatus("Import failed. " + error.message);
    }
  });
}

formEl.querySelectorAll('input[name="f-scope"]').forEach(function (el) {
  el.addEventListener("change", function () {
    setEditScope(selectedEditScope());
    formDeleteEl.textContent = selectedEditScope() === "occurrence" ? "Remove this day" : "Delete";
  });
});

document.addEventListener("visibilitychange", function () {
  if (!document.hidden) checkReminders();
});

fillTimeSelect(startEl, false);
fillTimeSelect(dueTimeEl, true);
ensureCategoryOptions();
reconnect();
