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
const WEEKDAYS = [0, 1, 2, 3, 4];
// One table drives the sidebar chips, the editor, setup and the grid colors.
// `kind` is what a new item of that type starts as; `preset` is the time it
// starts with when it is added without dragging a range on the calendar.
const CATEGORIES = [
  { id: "class", label: "School", color: "#3b82f6", kind: "locked", preset: { start: "08:00", end: "14:30", days: WEEKDAYS } },
  { id: "assignments", label: "Homework", color: "#ef4444", kind: "flexible", preset: { duration_min: 60 } },
  { id: "study", label: "Study", color: "#8b5cf6", kind: "flexible", preset: { duration_min: 60 } },
  { id: "exercise", label: "Sports", color: "#10b981", kind: "locked", preset: { start: "15:30", end: "17:00" } },
  { id: "extra", label: "Activity", color: "#ec4899", kind: "locked", preset: { start: "17:00", end: "18:00" } },
  { id: "meals", label: "Meals", color: "#f97316", kind: "locked", preset: { start: "18:00", end: "18:30" } },
  { id: "sleep", label: "Sleep", color: "#6366f1", kind: "locked", preset: { start: "22:00", end: "23:00" } },
  { id: "free", label: "Free", color: "#94a3b8", kind: "locked", preset: { start: "19:00", end: "20:00" } },
];
const KIND_LABEL = { locked: "Fixed time", flexible: "Flexible" };
// An "ok" slack needs no badge; its sentence still appears in the Solve results.
const SLACK_BADGE = { tight: "Tight fit", danger: "At risk" };

const EXPORT_FORMAT = "flexweek-week";
const EXPORT_VERSION = 1;
const REMINDER_WINDOW_MIN = 2;
const REMINDER_POLL_MS = 30000;
const LIVE_POLL_MS = 30000;
const ALARM_SNOOZE_MIN = 5;
const ALARM_SOUNDS = ["chime", "soft", "bright", "low", "glass", "spotify"];

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

function safeSpotifyUrl(value) {
  const text = String(value || "").trim();
  if (!/^https:\/\/open\.spotify\.com\/(track|playlist|album|episode|show)\/[A-Za-z0-9]+\/?(?:[?#].*)?$/.test(text)) {
    return "";
  }
  return text;
}

function pomodoroPlan(durationMin, workMin, breakMin, longBreakMin, cadence) {
  const values = [durationMin, workMin, breakMin, longBreakMin];
  if (values.some(function (value) {
    return !Number.isInteger(value) || value <= 0 || value % SNAP_MIN !== 0;
  })) return { error: "Grid splitting needs positive 15-minute work and break lengths." };
  const every = Math.max(2, Math.min(12, Number(cadence) || 4));
  let remaining = durationMin;
  let workIndex = 0;
  const segments = [];
  while (remaining > 0) {
    workIndex += 1;
    const length = Math.min(workMin, remaining);
    segments.push({ role: "work", duration_min: length, index: workIndex });
    remaining -= length;
    if (remaining > 0) {
      const long = workIndex % every === 0;
      segments.push({ role: "break", duration_min: long ? longBreakMin : breakMin, index: workIndex });
    }
  }
  return {
    segments: segments,
    total_min: segments.reduce(function (total, item) { return total + item.duration_min; }, 0),
  };
}

function freeIntervals(blocks, day) {
  const active = (blocks || []).filter(function (block) {
    return (block.missed_days || []).indexOf(day) === -1;
  });
  const intervals = occupiedIntervalsForDay(active, day).map(function (item) {
    return { startMin: Math.max(DAY_START_MIN, item.startMin), endMin: Math.min(DAY_END_MIN, item.endMin) };
  }).filter(function (item) { return item.endMin > item.startMin; });
  const merged = [];
  intervals.forEach(function (item) {
    const last = merged[merged.length - 1];
    if (last && item.startMin <= last.endMin) last.endMin = Math.max(last.endMin, item.endMin);
    else merged.push({ ...item });
  });
  const gaps = [];
  let cursor = DAY_START_MIN;
  merged.forEach(function (item) {
    if (item.startMin > cursor) gaps.push({ startMin: cursor, endMin: item.startMin });
    cursor = Math.max(cursor, item.endMin);
  });
  if (cursor < DAY_END_MIN) gaps.push({ startMin: cursor, endMin: DAY_END_MIN });
  return gaps;
}

function nowAndNext(blocks, day, minute) {
  const active = (blocks || []).filter(function (block) {
    return block.start && !block.completed && (block.missed_days || []).indexOf(day) === -1
      && occurrenceDays(block).indexOf(day) !== -1;
  }).slice().sort(function (a, b) { return parseStart(a.start) - parseStart(b.start); });
  let current = null;
  let next = null;
  active.forEach(function (block) {
    const start = parseStart(block.start);
    const end = start + block.duration_min;
    if (!current && start <= minute && minute < end) current = block;
    if (!next && start > minute) next = block;
  });
  return { current: current, next: next };
}

function alarmKey(date, alarm) {
  return [date, alarm.id, alarm.time].join("|");
}

function categoryById(category) {
  return CATEGORIES.find(function (item) { return item.id === category; }) || null;
}

function categoryLabel(category) {
  const found = categoryById(category);
  return found ? found.label : "";
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
  const allowed = new Set(["id", "title", "kind", "duration_min", "days", "priority", "energy",
    "earliest", "latest", "start", "course", "category", "completed", "completed_day", "missed_days",
    "spotify_url", "focus_sessions", "focus_minutes", "pomodoro_parent_id", "pomodoro_role", "pomodoro_index"]);
  if (Object.keys(block).some(function (key) { return !allowed.has(key); })) return at + " has an unknown field.";
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
  const texts = [["earliest", 40], ["latest", 40], ["course", 40], ["category", 32],
    ["spotify_url", 500], ["pomodoro_parent_id", 80]];
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
  if (block.spotify_url != null && !safeSpotifyUrl(block.spotify_url)) return at + " has a bad Spotify link.";
  for (const field of ["focus_sessions", "focus_minutes"]) {
    if (block[field] !== undefined && (!Number.isInteger(block[field]) || block[field] < 0)) {
      return at + " has a bad " + field + ".";
    }
  }
  if (block.focus_sessions > 9999 || block.focus_minutes > 71400) return at + " has excessive focus history.";
  if (block.pomodoro_role !== undefined && block.pomodoro_role !== "work" && block.pomodoro_role !== "break") {
    return at + " has a bad pomodoro role.";
  }
  if (block.pomodoro_index !== undefined && (
    !Number.isInteger(block.pomodoro_index) || block.pomodoro_index < 1 || block.pomodoro_index > 999
  )) return at + " has a bad pomodoro index.";
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
  for (let i = 0; i < blocks.length; i += 1) {
    const parentId = blocks[i].pomodoro_parent_id;
    if (parentId && seen.has(parentId)) {
      return "Export includes a task together with the focus chunks split from it.";
    }
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

function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return rest + " min";
  return hours + " h" + (rest ? " " + rest + " min" : "");
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
  const found = categoryById(category);
  return found ? found.color : null;
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
let prefs = {
  theme: "nocturne",
  reminders_enabled: false,
  reminder_lead_min: 5,
  reminder_sound: true,
  reminder_dnd_override: false,
  timer_work_min: 30,
  timer_break_min: 15,
  timer_long_break_min: 30,
  timer_long_break_every: 4,
  auto_split_pomodoro: false,
  default_spotify_url: null,
  alarms: [],
};
const firedReminders = new Set();
const activeNotifications = new Set();
let reminderTimer = null;
let lastReminderCheck = null;
const firedAlarms = new Set();
const snoozedAlarms = new Map();
let alarmTimer = null;
let liveTimer = null;
let lastAlarmCheck = null;
let activeAlarm = null;
let activeTone = null;
let focusTimer = null;
let focusState = null;
let focusBusy = false;
let pendingAlarms = [];
let alarmQueue = [];

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
      signedOut("Your session ended. Log in again; unsaved edits come back when you log in to the same account.");
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
  if (focusState && focusState.weekStart !== weekStart) resetFocusTimer();
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
  const fixed = blocks.filter(function (b) { return b.kind === "locked"; }).length;
  const flex = blocks.filter(function (b) { return b.kind === "flexible"; }).length;
  return fixed + " fixed, " + flex + " flexible";
}

function renderWeek() {
  document.getElementById("empty-week").hidden = weekState().blocks.length > 0;
  buildGrid(weekState().blocks);
}

function clearSolveResult(note = "Press Solve to place these around school and sports.") {
  weekState().trace = null;
  debugEl.hidden = true;
  debugChangesEl.hidden = true;
  debugMovesEl.replaceChildren();
  flexNoteEl.textContent = note;
}

/** The one refresh path after the week's blocks change: drop the stale solve, save, redraw. */
function commitWeek(note) {
  clearSolveResult(note);
  const saved = saveWeek();
  renderWeek();
  return saved;
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

/** A drag across empty grid opens the editor on that range. Nothing is added until it is saved. */
function requestCreate(day, startMin, endMin) {
  if (!account || saving) return false;
  const range = createDragRange(startMin, endMin);
  return range ? openCreateDialog(day, range.startMin, range.endMin) : false;
}

function requestCreateAt(day, startMin) {
  const range = createClickRange(startMin, occupiedIntervalsForDay(weekState().blocks, day));
  return range ? requestCreate(day, range.startMin, range.endMin) : false;
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
  commitWeek();
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
  commitWeek();
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
    } else if (action === "start-focus") {
      btn.hidden = !source || source.completed || source.pomodoro_role === "break" || !resolveFocusPlacement(blockId, day);
    } else if (action === "split-pomodoros") {
      // A task offered on several days would lose the others: the split writes
      // children on one day and replaces the source.
      btn.hidden = !source || source.completed || Boolean(source.pomodoro_role) ||
        isSeries(source) || !resolveFocusPlacement(blockId, day);
    } else if (action === "open-spotify") {
      btn.hidden = !source || !safeSpotifyUrl(source.spotify_url);
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
      if (gesture.moved) requestCreate(gesture.day, gesture.startMin, gesture.curMin);
      else requestCreateAt(gesture.day, gesture.startMin);
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
      openBlockEditor(source, day);
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
        (missed ? " missed-block" : "") + (block.completed ? " is-completed" : "") +
        (block.pomodoro_role === "break" ? " pomodoro-break" : "");
      el.dataset.id = block.id;
      el.dataset.day = String(day);
      el.style.top = ((clippedStart - visibleStart) / 60) * hourH + "rem";
      el.style.height = Math.max(((endMin - clippedStart) / 60) * hourH, 1.1) + "rem";
      const color = categoryColor(block.category);
      if (color) {
        el.style.borderLeftColor = color;
        el.style.borderLeftWidth = "4px";
      }
      el.title = block.title + " · " + KIND_LABEL[block.kind] + (block.course ? " · " + block.course : "") +
        (missed ? " · missed" : "") + " · double-click to edit";

      const title = document.createElement("div");
      title.className = "title";
      title.textContent = block.title;
      el.appendChild(title);

      const sub = document.createElement("div");
      sub.className = "sub";
      sub.textContent = formatDuration(block.duration_min) + (missed ? " · missed" : "") +
        (block.focus_sessions ? " · " + block.focus_sessions + " focus" : "");
      el.appendChild(sub);

      const spotify = safeSpotifyUrl(block.spotify_url);
      if (spotify) {
        const link = document.createElement("a");
        link.className = "spotify-link";
        link.href = spotify;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Spotify";
        link.addEventListener("pointerdown", function (event) { event.stopPropagation(); });
        link.addEventListener("click", function (event) { event.stopPropagation(); });
        el.appendChild(link);
      }

      const insight = insightFor(explanations, block.id);
      if (insight && SLACK_BADGE[insight.slack_status]) {
        const slack = document.createElement("span");
        slack.className = "slack-badge slack-" + insight.slack_status;
        slack.textContent = SLACK_BADGE[insight.slack_status];
        slack.title = insight.message;
        el.appendChild(slack);
      }

      if (selectedBlockId === block.id && selectedOccurrenceDay === day) {
        el.classList.add("is-selected");
      }

      lanes[day].appendChild(el);
    });
  });

  renderFreeGapOverlays(lanes, blocks);
  updateLiveDisplay();

  renderFlexible(blocks.filter((b) => b.kind === "flexible" && !b.start));
  renderFocusTasks();
}

function renderFlexible(flex) {
  flexibleEl.innerHTML = "";
  if (!flex.length) {
    // After Solve the note above the list already says every task was placed.
    if (weekState().trace) return;
    const empty = document.createElement("li");
    empty.className = "empty-note";
    empty.textContent = "No tasks yet. Pick Homework above, then drag on a day you can work on it.";
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

    pill(formatDuration(block.duration_min));
    if (block.latest) pill("due " + block.latest);
    if (block.category) pill(categoryLabel(block.category) || block.category);
    if (block.course) pill(block.course);
    // Homework priority and medium energy are the defaults, so only a change is worth a pill.
    if (block.priority && block.priority !== 3) pill(PRIORITY_LABEL[block.priority] || "P" + block.priority);
    if (block.energy && block.energy !== "medium") pill(block.energy + " energy");
    if (block.completed) pill("done");
    if (block.focus_sessions) pill(block.focus_sessions + " focus");

    li.appendChild(pills);
    const spotify = safeSpotifyUrl(block.spotify_url);
    if (spotify) {
      const link = document.createElement("a");
      link.className = "spotify-link";
      link.href = spotify;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Open Spotify";
      link.addEventListener("click", function (event) { event.stopPropagation(); });
      li.appendChild(link);
    }
    li.addEventListener("click", function () {
      const source = weekState().blocks.find(function (item) { return item.id === block.id; });
      if (source) openBlockEditor(source);
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
    if (source) openBlockEditor(source, day);
  });
  return button;
}

function solveSummary(trace) {
  const placed = (trace.placed || []).filter(function (block) { return block.kind === "flexible"; }).length;
  const waiting = (trace.unplaced || []).length;
  const total = placed + waiting;
  if (!total) return "No flexible tasks to place yet. Fixed times stay where they are.";
  const head = "Placed " + placed + " of " + total + (total === 1 ? " task." : " tasks.");
  if (!waiting) return head;
  return head + " " + waiting + (waiting === 1 ? " still needs" : " still need") + " a time. The reasons are below.";
}

function renderDebug(trace) {
  debugEl.hidden = false;
  debugStatsEl.textContent = solveSummary(trace);
  debugStatsEl.title = "Solved in " + Number(trace.solve_ms).toFixed(1) + " ms";
  debugUnplacedEl.innerHTML = "";
  (trace.explanations || []).forEach((item) => {
    const li = document.createElement("li");
    li.appendChild(detailButton(blockTitle(item.block_id) + " — " + item.message, item.block_id));
    debugUnplacedEl.appendChild(li);
  });
  if (!(trace.explanations || []).length) {
    const li = document.createElement("li");
    li.textContent = "Every task fits before its deadline.";
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

function applyPreferences(preferences) {
  prefs = {
    theme: preferences.theme || "nocturne",
    reminders_enabled: Boolean(preferences.reminders_enabled),
    reminder_lead_min: Number.isFinite(Number(preferences.reminder_lead_min))
      ? Number(preferences.reminder_lead_min) : 5,
    reminder_sound: preferences.reminder_sound !== false,
    reminder_dnd_override: Boolean(preferences.reminder_dnd_override),
    timer_work_min: Number(preferences.timer_work_min) || 30,
    timer_break_min: Number(preferences.timer_break_min) || 15,
    timer_long_break_min: Number(preferences.timer_long_break_min) || 30,
    timer_long_break_every: Number(preferences.timer_long_break_every) || 4,
    auto_split_pomodoro: Boolean(preferences.auto_split_pomodoro),
    default_spotify_url: safeSpotifyUrl(preferences.default_spotify_url) || null,
    alarms: Array.isArray(preferences.alarms) ? preferences.alarms.map(function (alarm) {
      return { ...alarm, spotify_url: safeSpotifyUrl(alarm.spotify_url) || null };
    }) : [],
  };
  themeEl.value = prefs.theme;
  document.documentElement.dataset.theme = prefs.theme;
  const enabled = document.getElementById("pref-reminders-enabled");
  const lead = document.getElementById("pref-reminder-lead");
  const sound = document.getElementById("pref-reminder-sound");
  const dnd = document.getElementById("pref-dnd-override");
  if (enabled) enabled.checked = prefs.reminders_enabled;
  if (lead) lead.value = String(prefs.reminder_lead_min);
  if (sound) sound.checked = prefs.reminder_sound;
  if (dnd) dnd.checked = prefs.reminder_dnd_override;
  const values = {
    "pref-theme": prefs.theme,
    "pref-timer-work": prefs.timer_work_min,
    "pref-timer-break": prefs.timer_break_min,
    "pref-timer-long-break": prefs.timer_long_break_min,
    "pref-timer-cadence": prefs.timer_long_break_every,
    "pref-spotify": prefs.default_spotify_url || "",
  };
  Object.keys(values).forEach(function (id) {
    const element = document.getElementById(id);
    if (element) element.value = String(values[id]);
  });
  const autoSplit = document.getElementById("pref-auto-split");
  if (autoSplit) autoSplit.checked = prefs.auto_split_pomodoro;
  renderAlarmList();
  syncReminderLoop();
  syncPhase7Loops();
}

function preferencesPayload() {
  return {
    theme: themeEl.value,
    reminders_enabled: prefs.reminders_enabled,
    reminder_lead_min: prefs.reminder_lead_min,
    reminder_sound: prefs.reminder_sound,
    reminder_dnd_override: prefs.reminder_dnd_override,
    timer_work_min: prefs.timer_work_min,
    timer_break_min: prefs.timer_break_min,
    timer_long_break_min: prefs.timer_long_break_min,
    timer_long_break_every: prefs.timer_long_break_every,
    auto_split_pomodoro: prefs.auto_split_pomodoro,
    default_spotify_url: prefs.default_spotify_url,
    alarms: prefs.alarms.map(function (alarm) { return { ...alarm }; }),
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
  commitWeek();
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
  commitWeek();
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
  return commitWeek();
}

function showReminderToast(message) {
  const toast = document.getElementById("reminder-toast");
  if (!toast) return;
  toast.hidden = false;
  toast.textContent = message;
  clearTimeout(showReminderToast._timer);
  showReminderToast._timer = setTimeout(function () { toast.hidden = true; }, 8000);
  if (showReminderToast._timer && typeof showReminderToast._timer.unref === "function") {
    showReminderToast._timer.unref();
  }
}

function playReminderSound() {
  if (!prefs.reminder_sound) return;
  soundOnce("chime");
}

function maybeNotify(title, body, soundEnabled = prefs.reminder_sound, tone = "chime") {
  showReminderToast(title + (body ? " — " + body : ""));
  if (soundEnabled) soundOnce(tone);
  if (typeof Notification !== "function") return;
  if (Notification.permission === "granted") {
    try {
      const stay = prefs.reminder_dnd_override;
      const notification = new Notification(title, {
        body: body || "", silent: true, requireInteraction: stay,
        tag: stay ? "flexweek-stay" : "flexweek",
      });
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

function scheduledBlocksForState(state) {
  if (!state) return [];
  if (!state.trace) return state.blocks.filter(function (block) {
    return block.kind === "locked" || (block.kind === "flexible" && block.start);
  });
  const sources = new Map(state.blocks.map(function (block) { return [block.id, block]; }));
  return (state.trace.placed || []).map(function (placed) {
    const source = sources.get(placed.id);
    return source ? { ...placed, ...source, days: placed.days, start: placed.start } : placed;
  });
}

function renderFreeGapOverlays(lanes, displayedBlocks) {
  const unplaced = weekState().trace && weekState().trace.unplaced || [];
  if (!unplaced.length) return;
  const hourH = hourHeightRem();
  for (let day = 0; day < 7; day += 1) {
    const needs = unplaced.filter(function (block) {
      return !block.completed && block.days.indexOf(day) !== -1;
    });
    if (!needs.length) continue;
    const shortest = Math.min(...needs.map(function (block) { return block.duration_min; }));
    freeIntervals(displayedBlocks, day).forEach(function (gap) {
      const length = gap.endMin - gap.startMin;
      if (length < shortest) return;
      const element = document.createElement("div");
      element.className = "free-gap";
      element.style.top = ((gap.startMin - DAY_START_MIN) / 60) * hourH + "rem";
      element.style.height = (length / 60) * hourH + "rem";
      element.textContent = "Free " + length + " min";
      lanes[day].appendChild(element);
    });
  }
}

function currentDateInfo(now) {
  const date = now || new Date();
  const iso = date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
  return {
    iso: iso,
    week: mondayOf(iso),
    day: (date.getDay() + 6) % 7,
    minute: date.getHours() * 60 + date.getMinutes(),
  };
}

function soundOnce(tone) {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = soundOnce._ctx || new Ctx();
    soundOnce._ctx = ctx;
    const recipes = {
      chime: [660, 880], soft: [440], bright: [880, 1175], low: [220, 330], glass: [1047, 1568],
    };
    const notes = recipes[tone] || recipes.chime;
    notes.forEach(function (frequency, index) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = tone === "soft" ? "sine" : "triangle";
      osc.frequency.value = frequency;
      gain.gain.value = tone === "soft" ? 0.025 : 0.04;
      osc.connect(gain);
      gain.connect(ctx.destination);
      const start = ctx.currentTime + index * 0.14;
      osc.start(start);
      osc.stop(start + 0.22);
    });
  } catch (err) { /* Audio is best-effort. */ }
}

function stopTone() {
  if (activeTone) clearInterval(activeTone);
  activeTone = null;
}

function openSpotify(value) {
  const url = safeSpotifyUrl(value);
  if (!url || typeof window.open !== "function") return false;
  try { return Boolean(window.open(url, "_blank", "noopener,noreferrer")); }
  catch (err) { return false; }
}

function startAlarmSound(alarm) {
  stopTone();
  const linked = alarm.sound === "spotify" && openSpotify(alarm.spotify_url || prefs.default_spotify_url);
  if (linked) return;
  const tone = alarm.sound === "spotify" ? "chime" : alarm.sound;
  soundOnce(tone);
  activeTone = setInterval(function () { soundOnce(tone); }, 2500);
  if (activeTone && typeof activeTone.unref === "function") activeTone.unref();
}

function presentNextAlarm() {
  if (activeAlarm || !alarmQueue.length) return;
  activeAlarm = alarmQueue.shift();
  const dialog = document.getElementById("alarm-dialog");
  document.getElementById("alarm-title").textContent = activeAlarm.name;
  document.getElementById("alarm-detail").textContent = activeAlarm.time + " · Alarm is ringing";
  const spotify = document.getElementById("alarm-open-spotify");
  const url = safeSpotifyUrl(activeAlarm.spotify_url || prefs.default_spotify_url);
  spotify.hidden = !url;
  spotify.dataset.url = url;
  startAlarmSound(activeAlarm);
  maybeNotify(activeAlarm.name, "Alarm · " + activeAlarm.time, false, activeAlarm.sound);
  if (dialog && typeof dialog.showModal === "function") dialog.showModal();
  else if (dialog) dialog.setAttribute("open", "open");
}

function queueAlarm(alarm) {
  if (activeAlarm && activeAlarm.id === alarm.id) return;
  if (alarmQueue.some(function (item) { return item.id === alarm.id; })) return;
  alarmQueue.push({ ...alarm });
  presentNextAlarm();
}

function finishAlarm(snooze) {
  if (!activeAlarm) return;
  if (snooze) snoozedAlarms.set(activeAlarm.id, Date.now() + ALARM_SNOOZE_MIN * 60000);
  stopTone();
  const dialog = document.getElementById("alarm-dialog");
  if (dialog && typeof dialog.close === "function") dialog.close();
  else if (dialog) dialog.removeAttribute("open");
  activeAlarm = null;
  presentNextAlarm();
}

function checkAlarms(nowDate) {
  if (!account) return;
  const now = nowDate || new Date();
  const nowMs = now.getTime();
  const startMs = lastAlarmCheck === null ? nowMs - REMINDER_WINDOW_MIN * 60000 : lastAlarmCheck;
  const info = currentDateInfo(now);
  prefs.alarms.forEach(function (alarm) {
    if (!alarm.enabled || alarm.days.indexOf(info.day) === -1) return;
    const parts = alarm.time.split(":").map(Number);
    const due = new Date(now.getFullYear(), now.getMonth(), now.getDate(), parts[0], parts[1]).getTime();
    const key = alarmKey(info.iso, alarm);
    if (startMs < due && due <= nowMs && !firedAlarms.has(key)) {
      firedAlarms.add(key);
      queueAlarm(alarm);
    }
  });
  snoozedAlarms.forEach(function (due, id) {
    if (!(startMs < due && due <= nowMs)) return;
    snoozedAlarms.delete(id);
    const alarm = prefs.alarms.find(function (item) { return item.id === id; });
    if (alarm && alarm.enabled) queueAlarm(alarm);
  });
  lastAlarmCheck = nowMs;
}

function renderAlarmList() {
  const list = document.getElementById("alarm-list");
  if (!list) return;
  list.replaceChildren();
  if (!pendingAlarms.length && prefs.alarms.length) pendingAlarms = prefs.alarms.map(function (alarm) { return { ...alarm }; });
  pendingAlarms.forEach(function (alarm) {
    const item = document.createElement("li");
    const text = document.createElement("span");
    text.textContent = alarm.name + " · " + alarm.time + " · " + alarm.days.map(function (day) { return DAYS[day]; }).join("/");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary";
    remove.textContent = "Remove";
    remove.addEventListener("click", function () {
      pendingAlarms = pendingAlarms.filter(function (item) { return item.id !== alarm.id; });
      renderAlarmList();
    });
    item.appendChild(text);
    item.appendChild(remove);
    list.appendChild(item);
  });
}

const TITLE_MAX = 80;

/** Keep a split child inside the same title limit the server enforces.
    A source at the limit would otherwise build a title the save rejects, and
    the split mutates the week before it saves, so the week could never save. */
function focusChildTitle(title, index, total) {
  const suffix = " · focus " + index + "/" + total;
  const room = TITLE_MAX - suffix.length;
  const head = Array.from(String(title));
  return (head.length > room ? head.slice(0, room).join("") : String(title)) + suffix;
}

function buildPomodoroBlocks(source, placed, plan) {
  const parentId = source.pomodoro_parent_id || source.id;
  let cursor = parseStart(placed.start);
  let firstWork = true;
  const totalWork = plan.segments.filter(function (segment) { return segment.role === "work"; }).length;
  return plan.segments.map(function (segment) {
    const carryHistory = segment.role === "work" && firstWork;
    const child = {
      ...cloneBlock(source),
      id: newId(),
      title: segment.role === "work"
        ? focusChildTitle(source.title, segment.index, totalWork)
        : "Pomodoro break",
      kind: "locked",
      days: [placed.days[0]],
      start: formatMinute(cursor),
      duration_min: segment.duration_min,
      completed: false,
      missed_days: [],
      focus_sessions: carryHistory ? (source.focus_sessions || 0) : 0,
      focus_minutes: carryHistory ? (source.focus_minutes || 0) : 0,
      pomodoro_parent_id: parentId,
      pomodoro_role: segment.role,
      pomodoro_index: segment.index,
      category: segment.role === "break" ? "free" : source.category,
      course: segment.role === "break" ? null : source.course,
      spotify_url: segment.role === "break" ? null : source.spotify_url,
      earliest: null,
      latest: null,
    };
    if (segment.role === "work") firstWork = false;
    delete child.completed_day;
    cursor += segment.duration_min;
    return child;
  });
}

function splitPlanForBlock(block) {
  return pomodoroPlan(
    block.duration_min,
    prefs.timer_work_min,
    prefs.timer_break_min,
    prefs.timer_long_break_min,
    prefs.timer_long_break_every,
  );
}

function canPlaceEnvelope(state, source, placed, totalMin) {
  const start = parseStart(placed.start);
  if (start + totalMin > DAY_END_MIN) return false;
  const scheduled = scheduledBlocksForState(state).filter(function (block) { return block.id !== source.id; });
  return occupiedIntervalsForDay(scheduled, placed.days[0]).every(function (item) {
    return start + totalMin <= item.startMin || start >= item.endMin;
  });
}

function splitBlockIntoPomodoros(blockId, day) {
  if (!account || saving) return false;
  const state = weekState();
  const index = state.blocks.findIndex(function (block) { return block.id === blockId; });
  const source = index >= 0 ? state.blocks[index] : null;
  const found = resolveFocusPlacement(blockId, day);
  if (!source || !found || source.completed || source.pomodoro_role || (source.kind === "locked" && isSeries(source))) {
    setStatus("Choose one placed, unfinished block to split.");
    return false;
  }
  const plan = splitPlanForBlock(source);
  if (plan.error) { setStatus(plan.error); return false; }
  const children = buildPomodoroBlocks(source, found.placed, plan);
  if (state.blocks.length - 1 + children.length > MAX_IMPORT_BLOCKS) {
    setStatus("Split would exceed the 100-block week limit.");
    return false;
  }
  if (!canPlaceEnvelope(state, source, found.placed, plan.total_min)) {
    setStatus("The focus chunks and breaks do not fit beside existing blocks.");
    return false;
  }
  state.blocks.splice(index, 1, ...children);
  commitWeek("Focus chunks and breaks are saved on the grid.");
  return true;
}

function autoSplitSolvedBlocks(trace) {
  const state = weekState();
  const replacements = new Map();
  let finalCount = state.blocks.length;
  state.blocks.forEach(function (source) {
    if (source.kind !== "flexible" || source.completed || source.pomodoro_role || source.duration_min <= prefs.timer_work_min) return;
    const placed = (trace.placed || []).find(function (item) { return item.id === source.id; });
    if (!placed || !placed.start) return;
    const plan = splitPlanForBlock(source);
    if (plan.error) return;
    const children = buildPomodoroBlocks(source, placed, plan);
    finalCount += children.length - 1;
    replacements.set(source.id, children);
  });
  if (!replacements.size) return 0;
  if (finalCount > MAX_IMPORT_BLOCKS) {
    setStatus("Automatic split skipped because it would exceed the 100-block week limit.");
    return 0;
  }
  state.blocks = state.blocks.flatMap(function (block) { return replacements.get(block.id) || [block]; });
  clearSolveResult("Automatic focus chunks are ready.");
  return replacements.size;
}

function solveInputBlocks(blocks) {
  if (!prefs.auto_split_pomodoro) return blocks;
  return blocks.map(function (block) {
    if (block.kind !== "flexible" || block.completed || block.pomodoro_role || block.duration_min <= prefs.timer_work_min) {
      return block;
    }
    const plan = splitPlanForBlock(block);
    if (plan.error) return block;
    return { ...block, duration_min: plan.total_min };
  });
}

function stopPhase7Loops() {
  if (alarmTimer) clearInterval(alarmTimer);
  if (liveTimer) clearInterval(liveTimer);
  alarmTimer = null;
  liveTimer = null;
  lastAlarmCheck = null;
}

function syncPhase7Loops() {
  stopPhase7Loops();
  if (!account) return;
  checkAlarms();
  updateLiveDisplay();
  if (typeof setInterval !== "function") return;
  alarmTimer = setInterval(function () { checkAlarms(); }, REMINDER_POLL_MS);
  liveTimer = setInterval(function () { updateLiveDisplay(); }, LIVE_POLL_MS);
  for (const timer of [alarmTimer, liveTimer]) {
    if (timer && typeof timer.unref === "function") timer.unref();
  }
}

document.getElementById("new-week").addEventListener("click", function () {
  if (!account || saving || !confirm("Clear " + weekLabel(selectedWeek) + "? This will be saved to your account.")) return;
  weekState().blocks = [];
  closeForm();
  commitWeek("Add school or sports as fixed times, then homework as flexible tasks.");
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
    "Every task has a time on the calendar.";
  const placed = trace.placed.filter(b => b.kind === "flexible").length;
  setStatus((weekState().dirty ? "Unsaved week · " : "Saved week · ") + placed + (placed === 1 ? " task placed" : " tasks placed"));
}

async function solveWeek() {
  if (!account || saving) return;
  const solveEpoch = epoch;
  saving = true;
  lockEditor(true);
  setStatus("Solving…");
  try {
    let trace = await api("/api/solve", { method: "POST", body: JSON.stringify({
      blocks: solveInputBlocks(weekState().blocks),
    }) });
    if (solveEpoch !== epoch) return;
    const splitCount = prefs.auto_split_pomodoro ? autoSplitSolvedBlocks(trace) : 0;
    if (splitCount) {
      saving = false;
      lockEditor(false);
      if (!await saveWeek() || solveEpoch !== epoch) return;
      saving = true;
      lockEditor(true);
      trace = await api("/api/solve", { method: "POST", body: JSON.stringify({ blocks: weekState().blocks }) });
      if (solveEpoch !== epoch) return;
    }
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
  if (await commitWeek()) {
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* A retry replaces the same blocks. */ }
    document.getElementById("import-panel").hidden = true;
  }
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
      if (source) openBlockEditor(source, Number.isInteger(day) ? day : null, "occurrence");
      return;
    }
    if (action === "edit-series") {
      if (source) openBlockEditor(source, Number.isInteger(day) ? day : null, "series");
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
    if (action === "start-focus") {
      startFocus(blockId, day);
      return;
    }
    if (action === "split-pomodoros") {
      splitBlockIntoPomodoros(blockId, day);
      return;
    }
    if (action === "open-spotify") {
      if (source) openSpotify(source.spotify_url);
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
    pendingAlarms = prefs.alarms.map(function (alarm) { return { ...alarm }; });
    applyPreferences(prefs);
    const accountText = document.getElementById("prefs-account");
    if (accountText) accountText.textContent = account ? "Signed in as " + account.username : "Signed out";
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
    const spotify = document.getElementById("pref-spotify").value.trim();
    if (spotify && !safeSpotifyUrl(spotify)) {
      const invalid = document.getElementById("prefs-error");
      invalid.hidden = false;
      invalid.textContent = "Use an https://open.spotify.com share link.";
      return;
    }
    const next = {
      theme: document.getElementById("pref-theme").value,
      reminders_enabled: Boolean(enabledEl && enabledEl.checked),
      reminder_lead_min: Math.max(0, Math.min(120, Number(leadEl && leadEl.value) || 0)),
      reminder_sound: Boolean(soundEl && soundEl.checked),
      reminder_dnd_override: Boolean(document.getElementById("pref-dnd-override").checked),
      timer_work_min: Math.max(1, Math.min(180, Number(document.getElementById("pref-timer-work").value) || 30)),
      timer_break_min: Math.max(1, Math.min(60, Number(document.getElementById("pref-timer-break").value) || 15)),
      timer_long_break_min: Math.max(1, Math.min(120, Number(document.getElementById("pref-timer-long-break").value) || 30)),
      timer_long_break_every: Math.max(2, Math.min(12, Number(document.getElementById("pref-timer-cadence").value) || 4)),
      auto_split_pomodoro: Boolean(document.getElementById("pref-auto-split").checked),
      default_spotify_url: spotify || null,
      alarms: pendingAlarms.map(function (alarm) { return { ...alarm }; }),
    };
    const err = document.getElementById("prefs-error");
    try {
      const saved = await api("/api/preferences", { method: "PUT", body: JSON.stringify(next) });
      if (preferenceEpoch !== epoch) return;
      applyPreferences(saved);
      themeEl.value = saved.theme;
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

const alarmAdd = document.getElementById("alarm-add");
if (alarmAdd) {
  alarmAdd.addEventListener("click", function () {
    const name = document.getElementById("alarm-name").value.trim();
    const time = document.getElementById("alarm-time").value;
    const sound = document.getElementById("alarm-sound").value;
    const spotify = document.getElementById("alarm-spotify").value.trim();
    const days = Array.from(document.querySelectorAll('input[name="alarm-day"]')).filter(function (item) {
      return item.checked;
    }).map(function (item) { return Number(item.value); });
    const error = document.getElementById("prefs-error");
    if (!name || !/^([01]\d|2[0-3]):[0-5]\d$/.test(time) || !days.length) {
      error.hidden = false;
      error.textContent = "Give the alarm a name, time, and at least one day.";
      return;
    }
    if (ALARM_SOUNDS.indexOf(sound) === -1 || (spotify && !safeSpotifyUrl(spotify))) {
      error.hidden = false;
      error.textContent = "Choose a built-in tone or a valid open.spotify.com link.";
      return;
    }
    if (pendingAlarms.length >= 20) {
      error.hidden = false;
      error.textContent = "You can save up to 20 alarms.";
      return;
    }
    pendingAlarms.push({
      id: newId(), name: name, time: time, days: days, enabled: true,
      sound: sound, spotify_url: spotify || null,
    });
    error.hidden = true;
    error.textContent = "";
    document.getElementById("alarm-name").value = "";
    renderAlarmList();
  });
}

const prefsSignOut = document.getElementById("prefs-sign-out");
if (prefsSignOut) prefsSignOut.addEventListener("click", function () {
  if (prefsDialog && typeof prefsDialog.close === "function") prefsDialog.close();
  document.getElementById("logout").click();
});

document.getElementById("alarm-dismiss").addEventListener("click", function () { finishAlarm(false); });
document.getElementById("alarm-snooze").addEventListener("click", function () { finishAlarm(true); });
document.getElementById("alarm-open-spotify").addEventListener("click", function (event) {
  openSpotify(event.currentTarget.dataset.url);
});
const alarmDialog = document.getElementById("alarm-dialog");
if (alarmDialog) alarmDialog.addEventListener("cancel", function (event) { event.preventDefault(); });

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

document.addEventListener("visibilitychange", function () {
  if (!document.hidden) checkReminders();
});
