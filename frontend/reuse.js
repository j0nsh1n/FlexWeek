// Stage 3 reuse and recovery. The browser and desktop app load this same file.

let stage3Clipboard = null;
let stage3Preview = null;
let stage3Busy = false;
const seenUnfinishedWeeks = new Set();
const stage3Attempts = new Map();

function stage3Attempt(key) {
  if (!stage3Attempts.has(key)) stage3Attempts.set(key, stage3OperationId());
  return stage3Attempts.get(key);
}

function finishStage3Attempt(key) {
  if (key) stage3Attempts.delete(key);
}

function stage3OperationId() {
  if (typeof crypto === "object" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return "00000000-0000-4000-8000-" + Date.now().toString(16).padStart(12, "0").slice(-12);
}

/** The server keeps restore point labels to 80 characters, so a long routine name is shortened to fit. */
function restorePointLabel(text) {
  const characters = Array.from(text);
  return characters.length <= 80 ? text : characters.slice(0, 79).join("") + "…";
}

function openStage3Dialog(dialog) {
  if (typeof dialog.showModal === "function") {
    if (!dialog.open) dialog.showModal();
  } else {
    dialog.open = true;
  }
}

function closeStage3Dialog(dialog) {
  if (typeof dialog.close === "function") dialog.close();
  else dialog.open = false;
}

function showStage3Error(id, message) {
  const target = document.getElementById(id);
  target.textContent = message || "";
  target.hidden = !message;
}

function stage3ActionDay() {
  if (Number.isInteger(selectedOccurrenceDay)) return selectedOccurrenceDay;
  if (plannerView === "day" && selectedDay && mondayOf(selectedDay) === selectedWeek) {
    return dayOffset(selectedWeek, selectedDay);
  }
  const today = currentDateInfo();
  return today.week === selectedWeek ? today.day : 0;
}

function stage3PasteDestination() {
  if (selectedBlockId && Number.isInteger(selectedOccurrenceDay)) {
    const state = weekState();
    const source = state.blocks.find(function (block) { return block.id === selectedBlockId; });
    if (source) {
      const placed = source.start ? source : state.trace && state.trace.placed.find(function (block) {
        return block.id === selectedBlockId && (block.days || []).indexOf(selectedOccurrenceDay) !== -1;
      });
      return { day: selectedOccurrenceDay, start: placed && placed.start ? placed.start : null };
    }
  }
  if (plannerView === "day" && selectedDay && mondayOf(selectedDay) === selectedWeek) {
    return { day: dayOffset(selectedWeek, selectedDay), start: null };
  }
  const today = currentDateInfo();
  return today.week === selectedWeek ? { day: today.day, start: null } : null;
}

function isHomeworkSession(block) {
  return Boolean(block && block.assignment_id);
}

function availableHomeworkMinutes(assignmentId, weekStart = selectedWeek) {
  const item = assignments.get(assignmentId);
  if (!item || item.completed) return 0;
  const later = plannedLater.get(weekStart);
  const here = sessionMinutes(weekState(weekStart).blocks).get(assignmentId) || 0;
  const remaining = Math.max(0, item.estimate_min - (item.focus_minutes || 0));
  const raw = Math.max(0, remaining - (later ? later.get(assignmentId) || 0 : 0) - here);
  return Math.floor(raw / SNAP_MIN) * SNAP_MIN;
}

function clipboardBlock(source, sourceDay, scope) {
  return {
    block: structuredClone(source), sourceDay: sourceDay,
    scope: scope, groupId: newId(),
  };
}

function setStage3Clipboard(kind, label, items) {
  const fingerprint = JSON.stringify(items.map(function (item) {
    return { block: item.block, sourceDay: item.sourceDay, scope: item.scope };
  }));
  stage3Clipboard = { kind: kind, label: label, items: items, fingerprint: fingerprint };
  refreshClipboardUI();
  setStatus(label + " copied. Choose a destination and paste.");
  return true;
}

function clearStage3Clipboard() {
  stage3Clipboard = null;
  refreshClipboardUI();
}

function refreshClipboardUI() {
  const summary = document.getElementById("clipboard-summary");
  const paste = document.getElementById("paste-day");
  const copy = document.getElementById("copy-day");
  const destination = stage3PasteDestination();
  const day = destination ? destination.day : null;
  summary.textContent = stage3Clipboard ? "Copied: " + stage3Clipboard.label : "Nothing copied";
  copy.textContent = day === null ? "Copy a selected day" : "Copy " + DAY_FULL[day];
  paste.textContent = day === null ? "Paste into a selected day" : "Paste into " + DAY_FULL[day];
  copy.disabled = !account || day === null;
  paste.disabled = !stage3Clipboard || !account || day === null;
}

function copyBlockById(blockId, day, scope = "auto") {
  if (!account) return false;
  const source = weekState().blocks.find(function (block) { return block.id === blockId; });
  if (!source) return false;
  const sourceDay = Number.isInteger(day) ? day : (source.days || [stage3ActionDay()])[0];
  const series = source.kind === "locked" && isSeries(source);
  const copyScope = scope === "auto" ? (series ? "occurrence" : "block") : scope;
  const label = copyScope === "series" ? source.title + " (all days)" :
    (series ? source.title + " (" + DAY_FULL[sourceDay] + " only)" : source.title);
  return setStage3Clipboard("block", label, [clipboardBlock(source, sourceDay, copyScope)]);
}

function selectedSource() {
  if (!selectedBlockId) return null;
  const block = weekState().blocks.find(function (item) { return item.id === selectedBlockId; });
  return block ? { block: block, day: selectedOccurrenceDay } : null;
}

function copySelectedBlock() {
  const source = selectedSource();
  if (!source) {
    setStatus("Select a block before copying it.");
    return false;
  }
  return copyBlockById(source.block.id, source.day, "auto");
}

function blockOccursOnCopiedDay(block, day) {
  if (isHomeworkSession(block) || block.kind === "flexible") {
    const placed = block.start ? block : weekState().trace && weekState().trace.placed.find(function (item) {
      return item.id === block.id && (item.days || []).indexOf(day) !== -1;
    });
    return Boolean(placed && placed.start && (placed.days || []).indexOf(day) !== -1);
  }
  return occurrenceDays(block).indexOf(day) !== -1;
}

function copyCurrentDay(day = null) {
  if (!account) return false;
  const destination = Number.isInteger(day) ? { day: day } : stage3PasteDestination();
  if (!destination) {
    setStatus("Select a block or open Day view before copying a day from this week.");
    return false;
  }
  day = destination.day;
  const items = weekState().blocks.filter(function (block) {
    return blockOccursOnCopiedDay(block, day) && !(isHomeworkSession(block) && block.completed);
  }).map(function (block) { return clipboardBlock(block, day, "occurrence"); });
  if (!items.length) {
    setStatus(DAY_FULL[day] + " has nothing to copy.");
    return false;
  }
  return setStage3Clipboard("day", DAY_FULL[day] + " · " + items.length +
    (items.length === 1 ? " item" : " items"), items);
}

function copiedFixedBlock(source, days, id) {
  const copy = structuredClone(source);
  copy.id = id;
  copy.kind = "locked";
  copy.days = days;
  copy.completed = false;
  copy.completed_day = null;
  copy.missed_days = [];
  copy.focus_minutes = 0;
  copy.focus_sessions = 0;
  delete copy.assignment_id;
  delete copy.pomodoro_parent_id;
  delete copy.pomodoro_role;
  return copy;
}

function copiedHomeworkBlock(source, assignment, day, duration, id) {
  return {
    id: id, kind: "flexible", title: assignment.title, duration_min: duration,
    days: [day], start: null, earliest: null, latest: null,
    priority: assignment.priority || 3, energy: assignment.energy || "medium",
    course: assignment.course || null, category: assignment.category || null,
    spotify_url: assignment.spotify_url || null, completed: false,
    completed_day: null, missed_days: [], assignment_id: assignment.id,
  };
}

function proposalsFromClipboard(targetDay, targetStart) {
  if (!stage3Clipboard) return [];
  const rows = [];
  // Copied sessions of one homework share what it has left, so one batch never over-plans it.
  const left = new Map();
  stage3Clipboard.items.forEach(function (item, itemIndex) {
    const source = item.block;
    if (isHomeworkSession(source)) {
      const assignment = assignments.get(source.assignment_id);
      if (!left.has(source.assignment_id)) left.set(source.assignment_id, availableHomeworkMinutes(source.assignment_id));
      const available = left.get(source.assignment_id);
      const duration = Math.min(source.duration_min, available);
      const usable = Boolean(assignment && duration >= SNAP_MIN);
      if (usable) left.set(source.assignment_id, available - duration);
      rows.push({
        weekStart: selectedWeek, day: targetDay, fixed: false,
        block: usable ? copiedHomeworkBlock(source, assignment, targetDay, duration, item.groupId) : structuredClone(source),
        groupId: item.groupId, checked: usable,
        invalid: assignment ? (usable ? "" : "No unplanned time remains for this homework.") :
          "This homework did not load.",
      });
      return;
    }
    const days = item.scope === "series" ? source.days.slice() : [targetDay];
    days.forEach(function (day, dayIndex) {
      const start = targetStart && stage3Clipboard.kind === "block" && item.scope !== "series"
        ? targetStart : source.start;
      const id = item.groupId;
      const block = copiedFixedBlock(source, [day], id);
      block.start = start;
      rows.push({
        weekStart: selectedWeek, day: day, fixed: true, block: block,
        groupId: item.scope === "series" ? item.groupId : item.groupId + "-" + itemIndex + "-" + dayIndex,
        originalDuration: source.duration_min, checked: true, invalid: start ? "" : "Choose a start time.",
      });
    });
  });
  return rows;
}

function intervalsOverlap(aStart, aEnd, bStart, bEnd) {
  return aStart < bEnd && bStart < aEnd;
}

function rowConflict(row, rows) {
  if (!row.fixed || !row.block.start) return null;
  const start = parseStart(row.block.start);
  const end = start + row.block.duration_min;
  const existing = weekState(row.weekStart).blocks.find(function (block) {
    if (!block.start || occurrenceDays(block).indexOf(row.day) === -1) return false;
    const otherStart = parseStart(block.start);
    return intervalsOverlap(start, end, otherStart, otherStart + block.duration_min);
  });
  if (existing) return existing.title;
  const other = rows.find(function (candidate) {
    if (candidate === row || !candidate.checked || !candidate.fixed || candidate.day !== row.day ||
        candidate.weekStart !== row.weekStart || !candidate.block.start) return false;
    const otherStart = parseStart(candidate.block.start);
    return intervalsOverlap(start, end, otherStart, otherStart + candidate.block.duration_min);
  });
  return other ? other.block.title : null;
}

function previewTimeSelect(row, rows) {
  const select = document.createElement("select");
  select.ariaLabel = "Start time for " + row.block.title;
  const last = DAY_END_MIN - row.block.duration_min;
  for (let minute = DAY_START_MIN; minute <= last; minute += SNAP_MIN) {
    const option = document.createElement("option");
    option.value = formatMinute(minute);
    option.textContent = formatMinute(minute);
    select.appendChild(option);
  }
  const current = row.block.start ? parseStart(row.block.start) : DAY_START_MIN;
  select.value = formatMinute(Math.min(current, last));
  row.block.start = select.value;
  select.addEventListener("change", function () {
    row.block.start = select.value;
    row.invalid = "";
    if (!rowConflict(row, rows)) row.checked = true;
    renderStage3Preview();
  });
  return select;
}

function previewDurationSelect(row, rows) {
  const select = document.createElement("select");
  select.ariaLabel = "Duration for " + row.block.title;
  const start = row.block.start ? parseStart(row.block.start) : DAY_START_MIN;
  const max = Math.min(DAY_END_MIN - start, row.originalDuration || row.block.duration_min);
  for (let minutes = SNAP_MIN; minutes <= max; minutes += SNAP_MIN) {
    const option = document.createElement("option");
    option.value = String(minutes);
    option.textContent = formatDuration(minutes);
    select.appendChild(option);
  }
  select.value = String(Math.min(row.block.duration_min, max));
  row.block.duration_min = Number(select.value);
  select.addEventListener("change", function () {
    row.block.duration_min = Number(select.value);
    if (!rowConflict(row, rows)) row.checked = true;
    renderStage3Preview();
  });
  return select;
}

function previewDaySelect(row, rows) {
  const select = document.createElement("select");
  select.ariaLabel = "Day for " + row.block.title;
  DAYS.forEach(function (day, index) {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = day;
    select.appendChild(option);
  });
  select.value = String(row.day);
  select.addEventListener("change", function () {
    row.day = Number(select.value);
    row.block.days = [row.day];
    if (!rowConflict(row, rows)) row.checked = true;
    renderStage3Preview();
  });
  return select;
}

function renderStage3Preview() {
  if (!stage3Preview) return;
  const list = document.getElementById("stage3-preview-list");
  list.replaceChildren();
  stage3Preview.rows.forEach(function (row) {
    const conflict = rowConflict(row, stage3Preview.rows);
    // Conflicting and invalid rows start unchecked; the student opts them back in after fixing them.
    if ((conflict || row.invalid) && row.firstRender !== false) row.checked = false;
    row.firstRender = false;
    const li = document.createElement("li");
    if (conflict) li.classList.add("has-conflict");
    const include = document.createElement("input");
    include.type = "checkbox";
    include.checked = row.checked;
    include.disabled = Boolean(row.invalid);
    include.ariaLabel = "Include " + row.block.title;
    include.addEventListener("change", function () {
      row.checked = include.checked;
      renderStage3Preview();
    });
    const title = document.createElement("strong");
    title.textContent = row.block.title;
    li.appendChild(include);
    li.appendChild(title);
    if (row.fixed) {
      li.appendChild(previewDaySelect(row, stage3Preview.rows));
      li.appendChild(previewTimeSelect(row, stage3Preview.rows));
      li.appendChild(previewDurationSelect(row, stage3Preview.rows));
    } else {
      const days = document.createElement("span");
      days.textContent = (row.block.days || [row.day]).map(function (day) { return DAYS[day]; }).join(", ");
      li.appendChild(days);
    }
    const detail = document.createElement("small");
    detail.className = "preview-detail";
    detail.textContent = row.invalid || (conflict ? "Conflicts with " + conflict + ". Choose another time." :
      (row.fixed ? formatDuration(row.block.duration_min) + " · Only this week" :
        formatDuration(row.block.duration_min) + " · Time chosen when you plan"));
    li.appendChild(detail);
    list.appendChild(li);
  });
  const selected = stage3Preview.rows.filter(function (row) { return row.checked; });
  const conflict = selected.some(function (row) { return Boolean(rowConflict(row, stage3Preview.rows)); });
  const capacityProblem = selected.length ? stage3CapacityProblem(stage3Preview) : "";
  const error = document.getElementById("stage3-preview-error");
  if (capacityProblem) {
    error.dataset.capacity = "true";
    showStage3Error("stage3-preview-error", capacityProblem);
  } else if (error.dataset.capacity === "true") {
    delete error.dataset.capacity;
    showStage3Error("stage3-preview-error", "");
  }
  document.getElementById("stage3-preview-confirm").disabled =
    stage3Busy || !selected.length || conflict || Boolean(capacityProblem);
}

function showStage3Preview(title, summary, rows, options = {}) {
  if (!rows.length) {
    setStatus("There is nothing available to add.");
    return false;
  }
  stage3Preview = {
    title: title, summary: summary, rows: rows,
    label: options.label || title.toLowerCase(), recoveryLabel: options.recoveryLabel || null,
    attemptKey: options.attemptKey || null,
    operationId: options.operationId || (options.attemptKey ? stage3Attempt(options.attemptKey) : stage3OperationId()),
    ids: new Map(), afterSave: options.afterSave || null,
  };
  document.getElementById("stage3-preview-title").textContent = title;
  document.getElementById("stage3-preview-summary").textContent = summary;
  showStage3Error("stage3-preview-error", "");
  renderStage3Preview();
  openStage3Dialog(document.getElementById("stage3-preview-dialog"));
  return true;
}

function previewBlocks(preview) {
  const groups = new Map();
  preview.rows.filter(function (row) { return row.checked; }).forEach(function (row) {
    const block = structuredClone(row.block);
    if (row.fixed) block.days = [row.day];
    const shape = structuredClone(block);
    delete shape.id;
    delete shape.days;
    const key = row.weekStart + "|" + row.groupId + "|" + JSON.stringify(shape);
    if (!groups.has(key)) groups.set(key, { weekStart: row.weekStart, block: block, days: [] });
    groups.get(key).days.push(row.day);
  });
  return Array.from(groups.entries()).map(function ([key, group]) {
    if (!preview.ids.has(key)) {
      const stem = preview.operationId.replace(/-/g, "").slice(0, 24);
      preview.ids.set(key, "b-stage3-" + stem + "-" + preview.ids.size.toString(36));
    }
    group.block.id = preview.ids.get(key);
    group.block.days = Array.from(new Set(group.days)).sort();
    return group;
  });
}

function stage3CapacityProblem(preview) {
  const additions = new Map();
  previewBlocks(preview).forEach(function (group) {
    additions.set(group.weekStart, (additions.get(group.weekStart) || 0) + 1);
  });
  for (const [weekStart, count] of additions) {
    if (weekState(weekStart).blocks.length + count > MAX_IMPORT_BLOCKS) {
      return weekLabel(weekStart) + " would exceed 100 blocks. Uncheck an item or remove a block first.";
    }
  }
  return "";
}

async function ensureStage3Week(weekStart) {
  if (weeks.has(weekStart)) return weekState(weekStart);
  const data = await api("/api/week?week_start=" + weekStart);
  const state = weekState(weekStart);
  state.blocks = data.blocks;
  state.revision = data.revision;
  state.dirty = false;
  state.conflict = false;
  noteLoaded("week", weekStart, data.blocks, data.revision, null);
  return state;
}

async function saveStage3Blocks(groups, preview) {
  const byWeek = new Map();
  groups.forEach(function (entry) {
    if (!byWeek.has(entry.weekStart)) byWeek.set(entry.weekStart, []);
    byWeek.get(entry.weekStart).push(entry.block);
  });
  for (const weekStart of byWeek.keys()) await ensureStage3Week(weekStart);
  const writes = [];
  const before = [];
  byWeek.forEach(function (added, weekStart) {
    const state = weekState(weekStart);
    const next = state.blocks.concat(added);
    if (next.length > MAX_IMPORT_BLOCKS) throw new Error(weekLabel(weekStart) + " would exceed 100 blocks.");
    before.push({ weekStart: weekStart, blocks: structuredClone(state.blocks) });
    writes.push({ week_start: weekStart, blocks: next, revision: state.revision });
  });
  const payload = { weeks: writes, assignments: [], operation_id: preview.operationId };
  if (preview.recoveryLabel) payload.snapshot_label = preview.recoveryLabel;
  const result = await api("/api/changes", { method: "POST", body: JSON.stringify(payload) });
  const historyWeeks = [];
  (result.weeks || []).forEach(function (saved) {
    const old = before.find(function (entry) { return entry.weekStart === saved.week_start; });
    historyWeeks.push({ weekStart: saved.week_start, before: old.blocks, after: structuredClone(saved.blocks) });
  });
  applyWritten(result);
  if (historyWeeks.length) pushStep({ label: preview.label, weeks: historyWeeks, assignments: [] });
  return result;
}

async function confirmStage3Preview() {
  if (!stage3Preview || stage3Busy || !account) return false;
  const selected = stage3Preview.rows.filter(function (row) { return row.checked; });
  if (!selected.length || selected.some(function (row) { return row.invalid || rowConflict(row, stage3Preview.rows); })) {
    showStage3Error("stage3-preview-error", "Resolve conflicts or select at least one item before saving.");
    return false;
  }
  const active = stage3Preview;
  const activeEpoch = epoch;
  stage3Busy = true;
  saving = true;
  lockEditor(true);
  renderStage3Preview();
  showStage3Error("stage3-preview-error", "");
  try {
    await saveStage3Blocks(previewBlocks(active), active);
    if (activeEpoch !== epoch) return false;
    closeStage3Dialog(document.getElementById("stage3-preview-dialog"));
    stage3Preview = null;
    clearSolveResult();
    renderWeekNav();
    renderWeek();
    refreshDayData();
    setStatus("Saved " + active.label + ". Undo brings it back.");
    finishStage3Attempt(active.attemptKey);
    if (typeof active.afterSave === "function") active.afterSave();
    return true;
  } catch (error) {
    if (activeEpoch === epoch && error.status === 409) {
      // Nothing was stored, so this attempt is over; saving again after a reload is a new operation.
      finishStage3Attempt(active.attemptKey);
      active.operationId = stage3OperationId();
      active.ids.clear();
      showStage3Error("stage3-preview-error",
        "The destination changed elsewhere. Cancel, reload the week, then paste or apply again.");
    } else if (activeEpoch === epoch) {
      showStage3Error("stage3-preview-error", error.message);
    }
    return false;
  } finally {
    if (activeEpoch === epoch) {
      saving = false;
      stage3Busy = false;
      lockEditor(false);
      if (stage3Preview) renderStage3Preview();
    }
  }
}

function pasteStage3Clipboard(targetDay = null, targetStart = undefined) {
  if (!account || !stage3Clipboard || stage3Busy) {
    if (!stage3Clipboard) setStatus("Copy a block or day before pasting.");
    return false;
  }
  const destination = Number.isInteger(targetDay)
    ? { day: targetDay, start: targetStart === undefined ? null : targetStart }
    : stage3PasteDestination();
  if (!destination) {
    setStatus("Select a block or open Day view before pasting into this week.");
    return false;
  }
  targetDay = destination.day;
  targetStart = destination.start;
  const rows = proposalsFromClipboard(targetDay, targetStart);
  return showStage3Preview("Preview paste", "Nothing changes until you save this preview.", rows,
    { label: stage3Clipboard.kind === "day" ? "the copied day" : "the copied block",
      attemptKey: "paste|" + account.id + "|" + selectedWeek + "|" + targetDay + "|" +
        (targetStart || "") + "|" + stage3Clipboard.fingerprint });
}

function duplicateBlockById(blockId, day, scope = "auto") {
  const prior = stage3Clipboard;
  if (!copyBlockById(blockId, day, scope)) return false;
  const opened = pasteStage3Clipboard(Number.isInteger(day) ? day : stage3ActionDay(), null);
  stage3Clipboard = prior;
  refreshClipboardUI();
  return opened;
}

function handleStage3Key(event) {
  if (!account || !(event.ctrlKey || event.metaKey) || event.altKey) return false;
  const target = event.target;
  if (target && typeof target.closest === "function" && target.closest("input, textarea, select, [contenteditable], dialog")) {
    return false;
  }
  // An open dialog owns the keyboard even when focus has fallen back to the page behind it.
  if (typeof document.querySelector === "function" && document.querySelector("dialog[open]")) return false;
  const key = String(event.key || "").toLowerCase();
  let handled = false;
  if (key === "c") handled = copySelectedBlock();
  else if (key === "v") handled = pasteStage3Clipboard();
  else if (key === "d") {
    const source = selectedSource();
    handled = source ? duplicateBlockById(source.block.id, source.day, "auto") : false;
    if (!source) setStatus("Select a block before duplicating it.");
  }
  if (handled) event.preventDefault();
  return handled;
}

function syncReuseContextMenu(source, series) {
  const menu = document.getElementById("block-context-menu");
  function hidden(action, value) {
    const button = menu.querySelector('button[data-action="' + action + '"]');
    if (button) button.hidden = value;
  }
  hidden("copy", series);
  hidden("copy-occurrence", !series);
  hidden("copy-series", !series);
  hidden("duplicate", series);
  hidden("duplicate-occurrence", !series);
  hidden("duplicate-series", !series);
  hidden("paste", !stage3Clipboard || !source);
}

function unfinishedForWeek(weekStart = selectedWeek) {
  if (!savedWeeks.some(function (saved) { return saved < weekStart; })) return [];
  return Array.from(assignments.values()).filter(function (item) {
    return !item.completed && availableHomeworkMinutes(item.id, weekStart) >= SNAP_MIN;
  }).sort(byDue);
}

function renderUnfinishedReview(force = false) {
  const panel = document.getElementById("unfinished-review");
  const list = document.getElementById("unfinished-list");
  const items = unfinishedForWeek();
  list.replaceChildren();
  items.forEach(function (item) {
    const minutes = availableHomeworkMinutes(item.id);
    const li = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = item.title;
    const detail = document.createElement("small");
    detail.textContent = formatDuration(minutes) + " left · due " + dueLabel(item.due);
    const action = document.createElement("div");
    action.className = "form-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary";
    button.textContent = "Plan here";
    button.addEventListener("click", function () { previewUnfinishedAssignment(item.id); });
    action.appendChild(button);
    li.appendChild(title);
    li.appendChild(detail);
    li.appendChild(action);
    list.appendChild(li);
  });
  panel.hidden = !items.length || (!force && seenUnfinishedWeeks.has(selectedWeek));
  document.getElementById("unfinished-open").disabled = !items.length;
  if (!panel.hidden) seenUnfinishedWeeks.add(selectedWeek);
  return items;
}

function maybeShowUnfinishedReview() {
  renderUnfinishedReview(false);
}

function previewUnfinishedAssignment(assignmentId) {
  const item = assignments.get(assignmentId);
  const minutes = availableHomeworkMinutes(assignmentId);
  if (!item || minutes < SNAP_MIN) {
    renderUnfinishedReview(true);
    setStatus("That homework is already fully planned.");
    return false;
  }
  const dueDay = dueDayInWeek(item.due.slice(0, 10));
  const days = daysThrough(dueDay, firstPlannableDay(selectedWeek));
  const block = copiedHomeworkBlock({}, item, days[0] === undefined ? 0 : days[0], minutes, newId());
  block.days = days.length ? days : [0];
  const row = { weekStart: selectedWeek, day: block.days[0], fixed: false, block: block,
    groupId: block.id, checked: true, invalid: "" };
  return showStage3Preview("Plan unfinished homework", item.title + " keeps its original deadline and progress.", [row], {
    label: "unfinished homework",
    attemptKey: "unfinished|" + account.id + "|" + selectedWeek + "|" + item.id + "|" + minutes,
    afterSave: function () { renderUnfinishedReview(true); },
  });
}

function prepareStage3Account() {
  clearStage3Clipboard();
  stage3Preview = null;
  if (typeof resetRoutineState === "function") resetRoutineState();
  if (typeof resetRestoreState === "function") resetRestoreState();
  seenUnfinishedWeeks.clear();
  stage3Attempts.clear();
  maybeShowUnfinishedReview();
}

function clearStage3State() {
  clearStage3Clipboard();
  stage3Preview = null;
  if (typeof resetRoutineState === "function") resetRoutineState();
  if (typeof resetRestoreState === "function") resetRestoreState();
  stage3Busy = false;
  seenUnfinishedWeeks.clear();
  stage3Attempts.clear();
  ["stage3-preview-dialog"].forEach(function (id) {
    closeStage3Dialog(document.getElementById(id));
  });
  document.getElementById("unfinished-review").hidden = true;
  document.getElementById("unfinished-list").replaceChildren();
}

document.addEventListener("keydown", handleStage3Key);
document.getElementById("copy-day").addEventListener("click", function () {
  document.getElementById("week-menu").open = false;
  copyCurrentDay();
});
document.getElementById("paste-day").addEventListener("click", function () {
  document.getElementById("week-menu").open = false;
  pasteStage3Clipboard();
});
document.getElementById("week-menu").addEventListener("toggle", refreshClipboardUI);
document.getElementById("stage3-preview-confirm").addEventListener("click", confirmStage3Preview);
document.getElementById("stage3-preview-cancel").addEventListener("click", function () {
  closeStage3Dialog(document.getElementById("stage3-preview-dialog"));
  stage3Preview = null;
});
document.getElementById("unfinished-dismiss").addEventListener("click", function () {
  document.getElementById("unfinished-review").hidden = true;
});
document.getElementById("unfinished-open").addEventListener("click", function () {
  document.getElementById("week-menu").open = false;
  renderUnfinishedReview(true);
});

document.getElementById("block-context-menu").addEventListener("click", function (event) {
  const button = event.target.closest ? event.target.closest("button[data-action]") : null;
  if (!button) return;
  const menu = document.getElementById("block-context-menu");
  const blockId = menu.dataset.id;
  const day = Number(menu.dataset.day);
  const source = weekState().blocks.find(function (block) { return block.id === blockId; });
  const action = button.dataset.action;
  if (action === "copy") copyBlockById(blockId, day, "block");
  else if (action === "copy-occurrence") copyBlockById(blockId, day, "occurrence");
  else if (action === "copy-series") copyBlockById(blockId, day, "series");
  else if (action === "duplicate") duplicateBlockById(blockId, day, "block");
  else if (action === "duplicate-occurrence") duplicateBlockById(blockId, day, "occurrence");
  else if (action === "duplicate-series") duplicateBlockById(blockId, day, "series");
  else if (action === "paste" && source) pasteStage3Clipboard(day, source.start || null);
});

refreshClipboardUI();
