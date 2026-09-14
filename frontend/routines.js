// Account-owned fixed-time routines for Stage 3.

const stage3Routines = new Map();
let routineBlockChoices = [];

function routineTemplate(block, templateId = newId()) {
  const template = {
    template_id: templateId, title: block.title, days: block.days.slice(),
    start: block.start, duration_min: block.duration_min,
  };
  ["category", "course", "priority", "energy", "spotify_url"].forEach(function (field) {
    if (block[field] !== undefined && block[field] !== null) template[field] = block[field];
  });
  return template;
}

function currentRoutineBlocks() {
  return weekState().blocks.filter(function (block) {
    return block.kind === "locked" && !block.assignment_id && !block.pomodoro_role;
  });
}

function renderRoutineChoices() {
  const list = document.getElementById("routine-blocks");
  list.replaceChildren();
  routineBlockChoices = currentRoutineBlocks().map(function (block) {
    const li = document.createElement("li");
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = true;
    label.appendChild(input);
    const text = document.createElement("span");
    text.textContent = block.title + " · " + block.days.map(function (day) { return DAYS[day]; }).join(", ") +
      " · " + block.start;
    label.appendChild(text);
    li.appendChild(label);
    list.appendChild(li);
    return { block: block, input: input, templateId: newId() };
  });
  if (!routineBlockChoices.length) {
    const li = document.createElement("li");
    li.textContent = "This week has no fixed commitments to save.";
    list.appendChild(li);
  }
}

function normalizeRoutine(data) {
  return data && data.routine ? data.routine : data;
}

async function loadStage3Routines() {
  const data = await api("/api/routines");
  stage3Routines.clear();
  ((data && data.routines) || []).forEach(function (routine) { stage3Routines.set(routine.id, routine); });
  renderRoutineList();
  return stage3Routines;
}

function selectedRoutineDays() {
  const days = [];
  for (let day = 0; day < 7; day += 1) {
    if (document.getElementById("routine-day-" + day).checked) days.push(day);
  }
  return days;
}

function routineRows(routine, weekStart, allowedDays) {
  const rows = [];
  (routine.blocks || []).forEach(function (template) {
    const groupId = newId();
    (template.days || []).filter(function (day) { return allowedDays.indexOf(day) !== -1; }).forEach(function (day) {
      const block = copiedFixedBlock({ ...template, kind: "locked" }, [day], groupId);
      delete block.template_id;
      rows.push({ weekStart: weekStart, day: day, fixed: true, block: block, groupId: groupId,
        originalDuration: template.duration_min, checked: true, invalid: "" });
    });
  });
  return rows;
}

async function applyRoutine(routineId) {
  if (!account || stage3Busy) return false;
  const routine = stage3Routines.get(routineId);
  const weekStart = document.getElementById("routine-destination").value;
  const allowed = selectedRoutineDays();
  showStage3Error("routine-error", "");
  if (!routine || !isWeekStart(weekStart)) {
    showStage3Error("routine-error", "Choose a destination date that is a Monday.");
    return false;
  }
  if (!allowed.length) {
    showStage3Error("routine-error", "Choose at least one weekday to copy.");
    return false;
  }
  try {
    await ensureStage3Week(weekStart);
    closeStage3Dialog(document.getElementById("routine-dialog"));
    return showStage3Preview("Apply " + routine.name, "Uncheck holidays or adjust one-off times before saving.",
      routineRows(routine, weekStart, allowed), {
        label: "the " + routine.name + " routine",
        recoveryLabel: "Before applying " + routine.name + " to " + weekStart,
        attemptKey: "routine|" + account.id + "|" + routine.id + "|" + routine.revision + "|" + weekStart + "|" + allowed.join(","),
        afterSave: function () { showWeek(weekStart); },
      });
  } catch (error) {
    showStage3Error("routine-error", error.message);
    return false;
  }
}

async function replaceRoutine(routine) {
  if (stage3Busy) return false;
  const selected = routineBlockChoices.filter(function (entry) { return entry.input.checked; });
  if (!selected.length) {
    showStage3Error("routine-error", "Select at least one fixed commitment.");
    return false;
  }
  if (!confirm("Replace " + routine.name + " with the selected fixed times from this week?")) return false;
  stage3Busy = true;
  try {
    const body = { id: routine.id, name: routine.name, blocks: selected.map(function (entry) {
      return routineTemplate(entry.block, entry.templateId);
    }), revision: routine.revision };
    const saved = normalizeRoutine(await api("/api/routines/" + encodeURIComponent(routine.id), {
      method: "PUT", body: JSON.stringify(body),
    }));
    stage3Routines.set(saved.id, saved);
    renderRoutineList();
    setStatus("Updated " + saved.name + ".");
    return true;
  } catch (error) {
    showStage3Error("routine-error", error.message);
    return false;
  } finally {
    stage3Busy = false;
  }
}

async function deleteRoutine(routine) {
  if (stage3Busy) return false;
  if (!confirm("Delete the saved routine " + routine.name + "?")) return false;
  const attemptKey = "delete-routine|" + account.id + "|" + routine.id + "|" + routine.revision;
  const operationId = stage3Attempt(attemptKey);
  stage3Busy = true;
  try {
    await api("/api/routines/" + encodeURIComponent(routine.id) + "?revision=" + routine.revision +
      "&operation_id=" + encodeURIComponent(operationId), { method: "DELETE" });
    stage3Routines.delete(routine.id);
    finishStage3Attempt(attemptKey);
    renderRoutineList();
    setStatus("Deleted " + routine.name + ".");
    return true;
  } catch (error) {
    showStage3Error("routine-error", error.message);
    return false;
  } finally {
    stage3Busy = false;
  }
}

function renderRoutineList() {
  const list = document.getElementById("routine-list");
  list.replaceChildren();
  if (!stage3Routines.size) {
    const empty = document.createElement("li");
    empty.textContent = "No routines saved yet.";
    list.appendChild(empty);
    return;
  }
  stage3Routines.forEach(function (routine) {
    const li = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = routine.name;
    const detail = document.createElement("small");
    detail.textContent = (routine.blocks || []).length + ((routine.blocks || []).length === 1 ? " fixed time" : " fixed times");
    const actions = document.createElement("div");
    actions.className = "form-actions";
    [["Apply", function () { applyRoutine(routine.id); }],
      ["Replace", function () { replaceRoutine(routine); }],
      ["Delete", function () { deleteRoutine(routine); }]].forEach(function (entry) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary";
      button.textContent = entry[0];
      button.addEventListener("click", entry[1]);
      actions.appendChild(button);
    });
    li.appendChild(title);
    li.appendChild(detail);
    li.appendChild(actions);
    list.appendChild(li);
  });
}

async function saveNewRoutine() {
  if (!account || stage3Busy) return false;
  const name = document.getElementById("routine-name").value.trim();
  const selected = routineBlockChoices.filter(function (entry) { return entry.input.checked; });
  showStage3Error("routine-error", "");
  if (!name || !selected.length) {
    showStage3Error("routine-error", "Name the routine and select at least one fixed commitment.");
    return false;
  }
  const fingerprint = JSON.stringify(selected.map(function (entry) {
    return { block: entry.block, templateId: entry.templateId };
  }));
  const attemptKey = "create-routine|" + account.id + "|" + name + "|" + fingerprint;
  const id = "r-" + stage3Attempt(attemptKey);
  stage3Busy = true;
  try {
    const saved = normalizeRoutine(await api("/api/routines/" + encodeURIComponent(id), {
      method: "PUT", body: JSON.stringify({
        id: id, name: name, blocks: selected.map(function (entry) {
          return routineTemplate(entry.block, entry.templateId);
        }), revision: 0,
      }),
    }));
    finishStage3Attempt(attemptKey);
    stage3Routines.set(saved.id, saved);
    document.getElementById("routine-name").value = "";
    renderRoutineList();
    setStatus("Saved " + saved.name + " as a reusable routine.");
    return true;
  } catch (error) {
    showStage3Error("routine-error", error.message);
    return false;
  } finally {
    stage3Busy = false;
  }
}

async function openRoutineDialog() {
  if (!account) return false;
  document.getElementById("week-menu").open = false;
  const prefsDialog = document.getElementById("prefs-dialog");
  if (prefsDialog.open) closeStage3Dialog(prefsDialog);
  document.getElementById("routine-destination").value = shiftWeek(selectedWeek, 1);
  for (let day = 0; day < 7; day += 1) document.getElementById("routine-day-" + day).checked = true;
  renderRoutineChoices();
  showStage3Error("routine-error", "");
  openStage3Dialog(document.getElementById("routine-dialog"));
  try { await loadStage3Routines(); }
  catch (error) { showStage3Error("routine-error", "Could not load routines. " + error.message); }
  return true;
}

function resetRoutineState() {
  stage3Routines.clear();
  routineBlockChoices = [];
  closeStage3Dialog(document.getElementById("routine-dialog"));
  renderRoutineList();
}

document.getElementById("routine-save-open").addEventListener("click", openRoutineDialog);
document.getElementById("routine-apply-open").addEventListener("click", openRoutineDialog);
document.getElementById("prefs-routines").addEventListener("click", openRoutineDialog);
document.getElementById("routine-save").addEventListener("click", saveNewRoutine);
document.getElementById("routine-close").addEventListener("click", function () {
  closeStage3Dialog(document.getElementById("routine-dialog"));
});

renderRoutineList();
