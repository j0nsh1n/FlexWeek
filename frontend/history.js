// Undo and redo for changes to weeks and homework (docs/stage1-contract.md, section 4).
// A step keeps, before and after, the blocks of each week it changed and the body of
// each assignment it changed. History lives in page memory, holds 50 steps, and is
// cleared on sign-out and account change.

const HISTORY_LIMIT = 50;
const undoSteps = [];
const redoSteps = [];
// What each week and assignment held when last recorded or loaded; a commit records the difference.
const committedWeeks = new Map();
const committedAssignments = new Map();

function sameValue(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function clearHistory() {
  undoSteps.length = 0;
  redoSteps.length = 0;
  committedWeeks.clear();
  committedAssignments.clear();
  renderHistoryButtons();
}

function renderHistoryButtons() {
  const undoEl = document.getElementById("undo");
  const redoEl = document.getElementById("redo");
  const lastUndo = undoSteps[undoSteps.length - 1];
  const lastRedo = redoSteps[redoSteps.length - 1];
  undoEl.hidden = !lastUndo;
  redoEl.hidden = !lastRedo;
  undoEl.title = lastUndo ? "Undo " + lastUndo.label + " (Ctrl+Z)" : "";
  redoEl.title = lastRedo ? "Redo " + lastRedo.label + " (Ctrl+Shift+Z)" : "";
}

function pushStep(step) {
  undoSteps.push(step);
  if (undoSteps.length > HISTORY_LIMIT) undoSteps.shift();
  redoSteps.length = 0;
  renderHistoryButtons();
  return step;
}

/** Record how a week and the unsaved homework changed since they were last recorded. */
function recordStep(label, weekStart = selectedWeek) {
  const step = { label: label, weeks: [], assignments: [] };
  const blocks = structuredClone(weekState(weekStart).blocks);
  const before = committedWeeks.get(weekStart);
  if (before && !sameValue(before, blocks)) step.weeks.push({ weekStart: weekStart, before: before, after: blocks });
  committedWeeks.set(weekStart, blocks);
  dirtyAssignments.forEach(function (id) {
    const item = assignments.get(id);
    const after = item ? assignmentBody(item) : null;
    const prior = committedAssignments.has(id) ? committedAssignments.get(id) : null;
    if (!sameValue(prior, after)) step.assignments.push({ id: id, before: prior, after: after });
    committedAssignments.set(id, after);
  });
  return step.weeks.length || step.assignments.length ? pushStep(step) : null;
}

/** Take the current state as recorded without a step, for changes Undo leaves alone, such as focus credit. */
function absorbIntoHistory(weekStart = selectedWeek) {
  committedWeeks.set(weekStart, structuredClone(weekState(weekStart).blocks));
  dirtyAssignments.forEach(function (id) {
    const item = assignments.get(id);
    committedAssignments.set(id, item ? assignmentBody(item) : null);
  });
}

/**
 * A week or assignment as the server holds it now. A revision other than the one this page
 * last knew means another device changed it, so older steps for it must not overwrite it.
 */
function noteLoaded(kind, key, value, revision, knownRevision) {
  if (Number.isInteger(knownRevision) && knownRevision !== revision) {
    undoSteps.concat(redoSteps).forEach(function (step) {
      const touched = kind === "week"
        ? (step.weeks || []).some(function (entry) { return entry.weekStart === key; })
        : (step.assignments || []).some(function (entry) { return entry.id === key; });
      if (touched) step.stale = true;
    });
  }
  (kind === "week" ? committedWeeks : committedAssignments).set(key, structuredClone(value));
}

/** Write weeks and homework: a single one with its own request, several in one all-or-nothing POST /api/changes. */
async function writeResources(weekWrites, assignmentWrites) {
  if (weekWrites.length + assignmentWrites.length > 1) {
    return api("/api/changes", { method: "POST", body: JSON.stringify({ weeks: weekWrites, assignments: assignmentWrites }) });
  }
  if (weekWrites.length) {
    return { weeks: [await api("/api/week", { method: "PUT", body: JSON.stringify(weekWrites[0]) })], assignments: [] };
  }
  const change = assignmentWrites[0];
  const path = "/api/assignments/" + encodeURIComponent(change.id);
  if (change.assignment) {
    const saved = await api(path, { method: "PUT", body: JSON.stringify({ ...change.assignment, revision: change.revision }) });
    return { weeks: [], assignments: [{ id: change.id, revision: saved.revision, assignment: saved }] };
  }
  const deleted = await api(path + "?revision=" + change.revision, { method: "DELETE" });
  return { weeks: [], assignments: [{ id: change.id, revision: change.revision, assignment: null, ...deleted }] };
}

/** Take what the server stored into the page, as the recorded state. */
function applyWritten(result) {
  (result.weeks || []).forEach(function (saved) {
    const state = weekState(saved.week_start);
    state.blocks = saved.blocks;
    state.revision = saved.revision;
    state.dirty = false;
    state.conflict = false;
    committedWeeks.set(saved.week_start, structuredClone(saved.blocks));
    rememberSavedWeek(saved.week_start);
  });
  (result.assignments || []).forEach(function (saved) {
    dirtyAssignments.delete(saved.id);
    if (saved.assignment) {
      const prior = assignments.get(saved.id) || { planned_min: 0, unplanned_min: 0 };
      // The server omits empty project details, so they default here before the merge;
      // otherwise a stale copy would keep details the student just undid away.
      assignments.set(saved.id, {
        ...prior, notes: "", links: [], checklist: [],
        ...saved.assignment, revision: saved.revision,
      });
      committedAssignments.set(saved.id, assignmentBody(assignments.get(saved.id)));
      return;
    }
    assignments.delete(saved.id);
    committedAssignments.set(saved.id, null);
    if (focusState && focusState.assignmentId === saved.id) resetFocusTimer();
    (saved.changed_weeks || []).forEach(function (changed) {
      const state = weeks.get(changed.week_start);
      if (!state) return;
      state.blocks = state.blocks.filter(function (block) { return block.assignment_id !== saved.id; });
      state.revision = changed.revision;
      committedWeeks.set(changed.week_start, structuredClone(state.blocks));
    });
  });
}

async function travelEdit(step, side) {
  const weekWrites = step.weeks.map(function (entry) {
    return { week_start: entry.weekStart, blocks: structuredClone(entry[side]), revision: weekState(entry.weekStart).revision };
  });
  const upserts = [];
  const removals = [];
  step.assignments.forEach(function (entry) {
    const current = assignments.get(entry.id);
    const target = entry[side];
    if (!target) {
      if (current) removals.push({ id: entry.id, assignment: null, revision: current.revision || 0 });
      return;
    }
    // Undo never takes away focus minutes counted since.
    const body = current
      ? { ...target, focus_minutes: current.focus_minutes || 0, focus_sessions: current.focus_sessions || 0 }
      : target;
    upserts.push({ id: entry.id, assignment: body, revision: current ? current.revision || 0 : 0 });
  });
  if (weekWrites.length || upserts.length) applyWritten(await writeResources(weekWrites, upserts));
  // Deleting an assignment also deletes its sessions in every week and bumps those revisions,
  // so removals go last, once the weeks above no longer hold its sessions. Homework that was
  // never saved exists only on this page.
  applyWritten({ assignments: removals.filter(function (change) { return !change.revision; }) });
  const stored = removals.filter(function (change) { return change.revision; });
  if (stored.length) applyWritten(await writeResources([], stored));
}

async function travelAssignmentDelete(step, side) {
  if (side === "after") {
    const current = assignments.get(step.id);
    if (!current) return;
    const result = await writeResources([], [{ id: step.id, assignment: null, revision: current.revision || 0 }]);
    step.removed = result.assignments[0].removed_sessions || {};
    applyWritten(result);
    return;
  }
  // Put the sessions back into each week as it is now, so newer work in those weeks stays.
  const weekWrites = [];
  for (const weekStart of Object.keys(step.removed)) {
    const current = weekStart === selectedWeek ? weekState() : await api("/api/week?week_start=" + weekStart);
    const present = new Set(current.blocks.map(function (block) { return block.id; }));
    weekWrites.push({
      week_start: weekStart,
      blocks: current.blocks.concat(step.removed[weekStart].filter(function (block) { return !present.has(block.id); })),
      revision: current.revision,
    });
  }
  applyWritten(await writeResources(weekWrites, [{ id: step.id, assignment: step.body, revision: 0 }]));
}

async function travel(from, to, side) {
  if (!account || saving || !from.length) return false;
  const step = from[from.length - 1];
  const verb = side === "before" ? "undo" : "redo";
  if (step.stale) {
    from.pop();
    renderHistoryButtons();
    setStatus((side === "before" ? "Undo" : "Redo") + " skipped " + step.label + ": it changed on another device since.");
    return false;
  }
  const travelEpoch = epoch;
  saving = true;
  lockEditor(true);
  setStatus(side === "before" ? "Undoing…" : "Redoing…");
  try {
    if (step.kind === "delete-assignment") await travelAssignmentDelete(step, side);
    else await travelEdit(step, side);
    if (travelEpoch !== epoch) return false;
    from.pop();
    to.push(step);
    clearSolveResult();
    renderWeek();
    renderHistoryButtons();
    setStatus((side === "before" ? "Undid " : "Redid ") + step.label + ".");
    refreshDayData();
    return true;
  } catch (error) {
    if (travelEpoch !== epoch) return false;
    if (error.status === 409) {
      // Nothing was stored and the step stays. The newer version wins; the usual actions reload it.
      if ((step.weeks || []).some(function (entry) { return entry.weekStart === selectedWeek; }) || step.removed) {
        weekState().conflict = true;
        saveActions.hidden = false;
      }
      setStatus("Could not " + verb + " " + step.label + ": it changed on another device. Reload the saved week to see the newer version.");
    } else {
      setStatus("Could not " + verb + " " + step.label + ". " + error.message);
    }
    renderWeek();
    return false;
  } finally {
    if (travelEpoch === epoch) {
      saving = false;
      lockEditor(false);
      document.getElementById("retry-save").disabled = weekState().conflict;
    }
  }
}

function undo() {
  return travel(undoSteps, redoSteps, "before");
}

function redo() {
  return travel(redoSteps, undoSteps, "after");
}

/** Delete a homework with its sessions in every week. Undo re-creates it and puts the sessions back. */
async function deleteAssignmentEverywhere(assignmentId) {
  const item = assignments.get(assignmentId);
  if (!account || saving || !item) return false;
  const label = "deleting " + item.title;
  if (!item.revision) {
    // The server has never stored it, so an undo would put back a session pointing at nothing.
    setStatus(item.title + " is not saved yet. Press Retry save, then delete it.");
    return false;
  }
  const deleteEpoch = epoch;
  const step = { kind: "delete-assignment", label: label, id: item.id, body: assignmentBody(item), removed: {} };
  saving = true;
  lockEditor(true);
  setStatus("Deleting " + item.title + "…");
  try {
    const result = await writeResources([], [{ id: item.id, assignment: null, revision: item.revision }]);
    if (deleteEpoch !== epoch) return false;
    step.removed = result.assignments[0].removed_sessions || {};
    applyWritten(result);
    pushStep(step);
    clearSolveResult();
    renderWeek();
    setStatus("Deleted " + item.title + " and its sessions in every week. Undo brings them back.");
    refreshDayData();
    return true;
  } catch (error) {
    if (deleteEpoch === epoch) setStatus("Not deleted. " + error.message);
    return false;
  } finally {
    if (deleteEpoch === epoch) {
      saving = false;
      lockEditor(false);
    }
  }
}

/** Ctrl/Cmd+Z undoes; Ctrl/Cmd+Shift+Z or Ctrl+Y redoes. A form field or dialog keeps its own keys. */
function handleHistoryKey(event) {
  if (!account || !(event.ctrlKey || event.metaKey) || event.altKey) return false;
  const target = event.target;
  if (target && typeof target.closest === "function" && target.closest("input, textarea, select, [contenteditable], dialog")) {
    return false;
  }
  // An open dialog owns the keyboard even when focus has fallen back to the page behind it.
  if (typeof document.querySelector === "function" && document.querySelector("dialog[open]")) return false;
  const key = String(event.key || "").toLowerCase();
  let action = null;
  if (key === "z") action = event.shiftKey ? redo : undo;
  else if (key === "y" && event.ctrlKey && !event.metaKey) action = redo;
  if (!action) return false;
  event.preventDefault();
  action();
  return true;
}

document.addEventListener("keydown", handleHistoryKey);
document.getElementById("undo").addEventListener("click", function () { undo(); });
document.getElementById("redo").addEventListener("click", function () { redo(); });
