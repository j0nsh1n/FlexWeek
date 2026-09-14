// Durable schedule restore points and protected Clear week for Stage 3.

let stage3RestorePreview = null;
let restorePoints = [];

async function clearWeekWithRestore() {
  if (!account || saving || !confirm("Clear " + weekLabel(selectedWeek) + "? A restore point and Undo will keep a way back.")) {
    return false;
  }
  const state = weekState();
  const before = structuredClone(state.blocks);
  const attemptKey = "clear|" + account.id + "|" + selectedWeek + "|" + state.revision;
  const operationId = stage3Attempt(attemptKey);
  const clearEpoch = epoch;
  saving = true;
  lockEditor(true);
  try {
    const result = await api("/api/changes", { method: "POST", body: JSON.stringify({
      weeks: [{ week_start: selectedWeek, blocks: [], revision: state.revision }], assignments: [],
      operation_id: operationId, snapshot_label: "Before clearing " + selectedWeek,
    }) });
    if (clearEpoch !== epoch) return false;
    applyWritten(result);
    finishStage3Attempt(attemptKey);
    pushStep({ label: "clearing the week", weeks: [{ weekStart: selectedWeek, before: before, after: [] }], assignments: [] });
    closeForm();
    clearSolveResult("Add school or sports as fixed times, then homework as flexible tasks.");
    renderWeek();
    setStatus("Cleared " + weekLabel(selectedWeek) + ". A restore point and Undo can bring it back.");
    return true;
  } catch (error) {
    if (clearEpoch === epoch) setStatus("The week was not cleared. " + error.message);
    return false;
  } finally {
    if (clearEpoch === epoch) { saving = false; lockEditor(false); }
  }
}

function restoreCount(group) {
  return (group.added || []).length + (group.changed || []).length + (group.removed || []).length;
}

function renderRestorePoints() {
  const list = document.getElementById("restore-list");
  list.replaceChildren();
  if (!restorePoints.length) {
    const empty = document.createElement("li");
    empty.textContent = "No restore points yet.";
    list.appendChild(empty);
    return;
  }
  restorePoints.forEach(function (point) {
    const li = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = point.label;
    const detail = document.createElement("small");
    const weekCount = point.week_count === undefined ? point.weeks : point.week_count;
    const assignmentCount = point.assignment_count === undefined ? point.assignments : point.assignment_count;
    detail.textContent = (point.created_at || "") + " · " + (weekCount || 0) + " weeks · " +
      (assignmentCount || 0) + " homework";
    const actions = document.createElement("div");
    actions.className = "form-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary";
    button.textContent = "Preview";
    button.addEventListener("click", function () { previewRestorePoint(point.id); });
    actions.appendChild(button);
    li.appendChild(title);
    li.appendChild(detail);
    li.appendChild(actions);
    list.appendChild(li);
  });
}

async function loadRestoreTools() {
  showStage3Error("restore-error", "");
  try {
    const results = await Promise.all([
      api("/api/storage-info"), api("/api/restore-points"),
    ]);
    if (!results[0] || typeof results[0].label !== "string") throw new Error("The server returned no storage location.");
    document.getElementById("storage-location").textContent = "Backups: " + results[0].label;
    restorePoints = (results[1] && results[1].restore_points) || (results[1] && results[1].points) || [];
    renderRestorePoints();
  } catch (error) {
    document.getElementById("storage-location").textContent = "Backup location unavailable";
    showStage3Error("restore-error", "Could not load restore points. " + error.message);
  }
}

async function createRestorePoint() {
  const input = document.getElementById("restore-label");
  const label = input.value.trim();
  if (!account || !label || stage3Busy) {
    showStage3Error("restore-error", "Give the restore point a name.");
    return false;
  }
  const attemptKey = "create-restore|" + account.id + "|" + label;
  const operationId = stage3Attempt(attemptKey);
  stage3Busy = true;
  document.getElementById("restore-create").disabled = true;
  try {
    const result = await api("/api/restore-points", { method: "POST", body: JSON.stringify({
      label: label, operation_id: operationId,
    }) });
    const point = result.restore_point || result;
    finishStage3Attempt(attemptKey);
    restorePoints = [point].concat(restorePoints.filter(function (item) { return item.id !== point.id; })).slice(0, 20);
    input.value = "";
    showStage3Error("restore-error", "");
    renderRestorePoints();
    setStatus("Saved restore point " + point.label + ".");
    return true;
  } catch (error) {
    showStage3Error("restore-error", error.message);
    return false;
  } finally {
    stage3Busy = false;
    document.getElementById("restore-create").disabled = false;
  }
}

function renderRestorePreview(data) {
  const changes = data.changes || { weeks: {}, assignments: {} };
  const weeks = changes.weeks || {};
  const homework = changes.assignments || {};
  document.getElementById("restore-preview-summary").textContent =
    restoreCount(weeks) + " week changes and " + restoreCount(homework) + " homework changes.";
  const detail = document.getElementById("restore-preview-detail");
  detail.replaceChildren();
  const grid = document.createElement("div");
  grid.className = "restore-diff";
  [["Added", (weeks.added || []).length + (homework.added || []).length],
    ["Changed", (weeks.changed || []).length + (homework.changed || []).length],
    ["Removed", (weeks.removed || []).length + (homework.removed || []).length]].forEach(function (entry) {
      const box = document.createElement("div");
      const count = document.createElement("strong");
      count.textContent = String(entry[1]);
      const label = document.createElement("span");
      label.textContent = entry[0];
      box.appendChild(count);
      box.appendChild(label);
      grid.appendChild(box);
    });
  detail.appendChild(grid);
  [["Weeks", [].concat(weeks.added || [], weeks.changed || [], weeks.removed || [])],
    ["Homework", [].concat(homework.added || [], homework.changed || [], homework.removed || [])]].forEach(function (entry) {
      if (!entry[1].length) return;
      const heading = document.createElement("h3");
      heading.textContent = entry[0];
      const list = document.createElement("ul");
      entry[1].forEach(function (item) {
        const li = document.createElement("li");
        li.textContent = typeof item === "string" ? item : (item.title || item.id);
        list.appendChild(li);
      });
      detail.appendChild(heading);
      detail.appendChild(list);
    });
}

async function previewRestorePoint(id) {
  showStage3Error("restore-preview-error", "");
  try {
    const data = await api("/api/restore-points/" + encodeURIComponent(id) + "/preview");
    stage3RestorePreview = { ...data, operationId: stage3Attempt("restore|" + account.id + "|" + id + "|" + data.state_token),
      attemptKey: "restore|" + account.id + "|" + id + "|" + data.state_token };
    renderRestorePreview(data);
    openStage3Dialog(document.getElementById("restore-preview-dialog"));
    return true;
  } catch (error) {
    showStage3Error("restore-error", "Could not preview that restore point. " + error.message);
    return false;
  }
}

async function validateFocusAfterRestore(target) {
  if (!target || !target.blockId || !focusState) return;
  if (!account) {
    resetFocusTimer();
    return;
  }
  try {
    const week = target.weekStart === selectedWeek ? weekState() : await api("/api/week?week_start=" + target.weekStart);
    const exists = week.blocks.some(function (block) {
      return block.id === target.blockId && (!target.assignmentId || block.assignment_id === target.assignmentId);
    });
    if (!exists) {
      resetFocusTimer();
      forgetFocus(account.id);
      setStatus("Schedule restored. The previous focus timer was stopped because its session no longer exists.");
    }
  } catch {
    resetFocusTimer();
    forgetFocus(account.id);
  }
}

async function restoreFromPreview() {
  if (!stage3RestorePreview || stage3Busy || !account) return false;
  const preview = stage3RestorePreview;
  const identity = { ...account };
  const focusTarget = focusState ? { weekStart: focusState.weekStart, blockId: focusState.blockId,
    assignmentId: focusState.assignmentId } : null;
  stage3Busy = true;
  document.getElementById("restore-confirm").disabled = true;
  showStage3Error("restore-preview-error", "");
  try {
    await api("/api/restore-points/" + encodeURIComponent(preview.id) + "/restore", {
      method: "POST", body: JSON.stringify({ state_token: preview.state_token, operation_id: preview.operationId }),
    });
    closeStage3Dialog(document.getElementById("restore-preview-dialog"));
    stage3RestorePreview = null;
    finishStage3Attempt(preview.attemptKey);
    clearStage3Clipboard();
    seenUnfinishedWeeks.clear();
    clearHistory();
    await loadAccount(identity);
    if (!account) return true;
    await validateFocusAfterRestore(focusTarget);
    setStatus("Schedule restored. A recovery point keeps the schedule it replaced.");
    return true;
  } catch (error) {
    if (error.status === 409) {
      finishStage3Attempt(preview.attemptKey);
      showStage3Error("restore-preview-error", "Your schedule changed after this preview. The preview has been refreshed.");
      try {
        const refreshed = await api("/api/restore-points/" + encodeURIComponent(preview.id) + "/preview");
        stage3RestorePreview = { ...refreshed,
          attemptKey: "restore|" + account.id + "|" + preview.id + "|" + refreshed.state_token,
          operationId: stage3Attempt("restore|" + account.id + "|" + preview.id + "|" + refreshed.state_token) };
        renderRestorePreview(stage3RestorePreview);
      } catch (refreshError) {
        showStage3Error("restore-preview-error", "Could not refresh the preview. " + refreshError.message);
      }
    } else {
      showStage3Error("restore-preview-error", "Nothing was restored. " + error.message);
    }
    return false;
  } finally {
    stage3Busy = false;
    document.getElementById("restore-confirm").disabled = false;
  }
}

function resetRestoreState() {
  stage3RestorePreview = null;
  restorePoints = [];
  closeStage3Dialog(document.getElementById("restore-preview-dialog"));
  renderRestorePoints();
}

document.getElementById("restore-create").addEventListener("click", createRestorePoint);
document.getElementById("restore-confirm").addEventListener("click", restoreFromPreview);
document.getElementById("restore-cancel").addEventListener("click", function () {
  closeStage3Dialog(document.getElementById("restore-preview-dialog"));
  stage3RestorePreview = null;
});

document.getElementById("prefs-open").addEventListener("click", function () { loadRestoreTools(); });

renderRestorePoints();
