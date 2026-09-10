// The block editor. A dialog reads the form into a draft, checks the draft, and
// turns it into a block patch. Drafts have this shape:
//   { id, kind, category, title, day, days, startMin, endMin, duration_min,
//     dueDay, dueTime, priority, energy, course, spotify_url, completed }
// `day`, `startMin` and `endMin` describe a fixed time; `duration_min`, `dueDay`
// and `dueTime` describe a flexible task. `days` is when it happens (fixed) or
// which days Solve may use (flexible), which is not the same as the due day.

const formEl = document.getElementById("block-form");
const blockDialogEl = document.getElementById("block-dialog");
const formErrorEl = document.getElementById("form-error");
const formHeadingEl = document.getElementById("form-heading");
const formDeleteEl = document.getElementById("form-delete");
const formMissedEl = document.getElementById("form-missed");
const startEl = document.getElementById("f-start");
const endEl = document.getElementById("f-end");
const dueTimeEl = document.getElementById("f-due-time");
const DURATION_CHOICES = [15, 30, 45, 60, 90, 120, 150, 180, 240, 300, 360];

let editingOccurrenceDay = null;
let editingScope = "series";
let editingExisting = false;
// Flexible days follow the due day until the student picks days themselves.
let flexDaysTouched = false;
let addType = "assignments";

function field(id) {
  return document.getElementById(id);
}

function daysThrough(dueDay) {
  const last = Number.isInteger(dueDay) ? dueDay : 6;
  return DAYS.map(function (_name, day) { return day; }).filter(function (day) { return day <= last; });
}

function dayList(days) {
  if (days.length === 7) return "any day this week";
  const names = days.map(function (day) { return DAY_FULL[day]; });
  if (names.length === 1) return names[0];
  return names.slice(0, -1).join(", ") + " or " + names[names.length - 1];
}

function newDraft(category, day, startMin, endMin) {
  const type = categoryById(category);
  return {
    id: null, kind: type ? type.kind : "locked", category: type ? type.id : null, title: "",
    day: day, days: [day], startMin: startMin, endMin: endMin,
    duration_min: Math.max(SNAP_MIN, endMin - startMin), dueDay: null, dueTime: "21:00",
    priority: 3, energy: "medium", course: "", spotify_url: "", completed: false,
  };
}

/** A draft for "Add without dragging": the type's preset, on today when this week is open. */
function presetDraft(category, weekStart, now) {
  const type = categoryById(category) || CATEGORIES[0];
  const info = currentDateInfo(now);
  const day = weekStart === info.week ? info.day : 0;
  const preset = type.preset || {};
  if (type.kind === "flexible") {
    const draft = newDraft(type.id, day, DAY_START_MIN, DAY_START_MIN + (preset.duration_min || 60));
    draft.days = daysThrough(null);
    return draft;
  }
  const draft = newDraft(type.id, day, parseStart(preset.start), parseStart(preset.end));
  if (preset.days) draft.days = preset.days.slice();
  if (draft.days.indexOf(day) === -1) draft.day = draft.days[0];
  return draft;
}

function draftFromBlock(block, occurrenceDay) {
  const latest = parseLatest(block.latest);
  const startMin = block.start ? parseStart(block.start) : DAY_START_MIN;
  return {
    id: block.id, kind: block.kind, category: block.category || null, title: block.title,
    day: Number.isInteger(occurrenceDay) ? occurrenceDay : block.days[0], days: block.days.slice(),
    startMin: startMin, endMin: Math.min(DAY_END_MIN, startMin + block.duration_min),
    duration_min: block.duration_min, dueDay: latest.day === "" ? null : Number(latest.day),
    dueTime: latest.time || "21:00", priority: block.priority || 3, energy: block.energy || "medium",
    course: block.course || "", spotify_url: block.spotify_url || "", completed: Boolean(block.completed),
  };
}

/** The first thing wrong with a draft, named by the field to send the student to. */
function draftProblem(draft) {
  if (textLength(draft.title.trim()) > 80) {
    return { field: "f-title", message: "Keep the title to 80 characters or fewer." };
  }
  if (!draft.days.length) {
    return { field: "f-days", message: draft.kind === "locked"
      ? "Pick at least one day it happens."
      : "Pick at least one day FlexWeek can use for it." };
  }
  if (draft.kind === "locked") {
    if (draft.endMin <= draft.startMin) return { field: "f-end", message: "The end time must be after the start time." };
  } else {
    if (!Number.isInteger(draft.duration_min) || draft.duration_min <= 0 || draft.duration_min % SNAP_MIN) {
      return { field: "f-duration", message: "Choose how much time it needs." };
    }
    if (Number.isInteger(draft.dueDay)) {
      const usable = draft.days.filter(function (day) { return day <= draft.dueDay; });
      if (!usable.length) {
        return { field: "f-days", message: "It is due " + DAY_FULL[draft.dueDay] +
          ", but every day you picked comes after that. Pick an earlier day or a later due day." };
      }
      const roomOnDueDay = parseStart(draft.dueTime) - DAY_START_MIN;
      if (usable.every(function (day) { return day === draft.dueDay; }) && roomOnDueDay < draft.duration_min) {
        return { field: "f-due-time", message: "There are not " + formatDuration(draft.duration_min) +
          " between 06:00 and " + draft.dueTime + " on " + DAY_FULL[draft.dueDay] + ". Pick a later due time or an earlier day." };
      }
    }
  }
  if (draft.spotify_url.trim() && !safeSpotifyUrl(draft.spotify_url)) {
    return { field: "f-spotify", message: "Use an https://open.spotify.com share link." };
  }
  return null;
}

function draftPatch(draft) {
  const locked = draft.kind === "locked";
  return {
    title: draft.title.trim() || categoryLabel(draft.category) || (locked ? "Fixed time" : "Task"),
    duration_min: locked ? draft.endMin - draft.startMin : draft.duration_min,
    days: draft.days.slice().sort(function (a, b) { return a - b; }),
    priority: draft.priority,
    energy: draft.energy,
    course: draft.course.trim() || null,
    category: draft.category || null,
    completed: draft.completed,
    spotify_url: draft.spotify_url.trim() || null,
    earliest: null,
    latest: !locked && Number.isInteger(draft.dueDay) ? DAY_FULL[draft.dueDay] + " " + draft.dueTime : null,
    start: locked ? formatMinute(draft.startMin) : null,
  };
}

function flexSummary(draft) {
  if (!draft.days.length) return "Pick at least one day under More options.";
  const due = Number.isInteger(draft.dueDay)
    ? " It is due " + DAY_FULL[draft.dueDay] + " at " + draft.dueTime + "."
    : " It has no due time.";
  return "Solve will find " + formatDuration(draft.duration_min) + " for it on " + dayList(draft.days) + "." + due;
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

function fillOptions(select, entries) {
  select.innerHTML = "";
  entries.forEach(function (entry) {
    const option = document.createElement("option");
    option.value = String(entry[0]);
    option.textContent = entry[1];
    select.appendChild(option);
  });
}

function fillDurationSelect(current) {
  const choices = DURATION_CHOICES.indexOf(current) === -1 && current > 0
    ? DURATION_CHOICES.concat([current]).sort(function (a, b) { return a - b; })
    : DURATION_CHOICES;
  fillOptions(field("f-duration"), choices.map(function (minutes) { return [minutes, formatDuration(minutes)]; }));
}

function fillEditorSelects() {
  const starts = slotTimes().map(function (time) { return [time, time]; });
  fillOptions(startEl, starts);
  fillOptions(endEl, starts.slice(1).concat([[formatMinute(DAY_END_MIN), formatMinute(DAY_END_MIN)]]));
  fillOptions(dueTimeEl, starts.concat([[formatMinute(DAY_END_MIN), formatMinute(DAY_END_MIN)]]));
  fillOptions(field("f-when-day"), DAY_FULL.map(function (name, day) { return [day, name]; }));
  fillOptions(field("f-category"), [["", "None"]].concat(CATEGORIES.map(function (cat) { return [cat.id, cat.label]; })));
  fillDurationSelect(60);
}

function selectedKind() {
  return field("f-kind-flexible").checked ? "flexible" : "locked";
}

function selectedEditScope() {
  return field("f-scope-series").checked ? "series" : "occurrence";
}

function selectedDays() {
  return DAYS.map(function (_name, day) { return day; }).filter(function (day) {
    return field("f-day-" + day).checked;
  });
}

function setSelectedDays(days) {
  DAYS.forEach(function (_name, day) { field("f-day-" + day).checked = days.indexOf(day) !== -1; });
}

function readDraft() {
  const kind = selectedKind();
  const whenDay = Number(field("f-when-day").value);
  let days = selectedDays();
  if (kind === "locked") {
    days = editingScope === "occurrence" && editingOccurrenceDay !== null
      ? [editingOccurrenceDay]
      : Array.from(new Set(days.concat([whenDay])));
  }
  const due = field("f-due-day").value;
  return {
    id: field("f-id").value || null,
    kind: kind,
    category: field("f-category").value || null,
    title: field("f-title").value,
    day: whenDay,
    days: days,
    startMin: parseStart(startEl.value),
    endMin: parseStart(endEl.value),
    duration_min: Number(field("f-duration").value),
    dueDay: due === "" ? null : Number(due),
    dueTime: dueTimeEl.value || "21:00",
    priority: Number(field("f-priority").value) || 3,
    energy: field("f-energy").value || "medium",
    course: field("f-course").value,
    spotify_url: field("f-spotify").value,
    completed: Boolean(field("f-completed").checked),
  };
}

function writeDraft(draft) {
  field("f-id").value = draft.id || "";
  field("f-kind-locked").checked = draft.kind === "locked";
  field("f-kind-flexible").checked = draft.kind === "flexible";
  field("f-category").value = draft.category || "";
  field("f-title").value = draft.title;
  field("f-when-day").value = String(draft.day);
  startEl.value = formatMinute(draft.startMin);
  endEl.value = formatMinute(draft.endMin);
  fillDurationSelect(draft.duration_min);
  field("f-duration").value = String(draft.duration_min);
  field("f-due-day").value = Number.isInteger(draft.dueDay) ? String(draft.dueDay) : "";
  dueTimeEl.value = draft.dueTime;
  setSelectedDays(draft.days);
  field("f-priority").value = String(draft.priority);
  field("f-energy").value = draft.energy;
  field("f-course").value = draft.course;
  field("f-spotify").value = draft.spotify_url;
  field("f-completed").checked = draft.completed;
}

/** Show the fields that fit the chosen kind and scope, and refresh the plain-English summary. */
function syncEditor() {
  const kind = selectedKind();
  const locked = kind === "locked";
  const occurrenceOnly = editingScope === "occurrence" && editingOccurrenceDay !== null;
  field("f-locked-fields").hidden = !locked;
  field("f-flex-fields").hidden = locked;
  field("f-flex-advanced").hidden = locked;
  field("f-kind-locked").disabled = editingExisting;
  field("f-kind-flexible").disabled = editingExisting;
  field("f-days-legend").textContent = locked ? "Repeats on" : "Days Solve may use";
  field("f-days-help").textContent = locked
    ? "The day chosen above is always included."
    : "The due day only sets the deadline. These are the days it can go on.";
  const whenDay = Number(field("f-when-day").value);
  field("f-when-day").disabled = occurrenceOnly;
  DAYS.forEach(function (_name, day) {
    const box = field("f-day-" + day);
    if (locked && occurrenceOnly) box.checked = day === editingOccurrenceDay;
    else if (locked && day === whenDay) box.checked = true;
    box.disabled = locked && (occurrenceOnly || day === whenDay);
  });
  const type = categoryById(field("f-category").value);
  field("f-title").placeholder = type ? type.label : (locked ? "Fixed time" : "Task");
  field("f-flex-summary").textContent = locked ? "" : flexSummary(readDraft());
  renderCategoryChips(field("category-chips"), field("f-category").value, pickDialogCategory);
}

function showFormError(problem) {
  formEl.querySelectorAll("[aria-invalid]").forEach(function (el) { el.removeAttribute("aria-invalid"); });
  if (!problem) {
    formErrorEl.hidden = true;
    formErrorEl.textContent = "";
    return;
  }
  formErrorEl.hidden = false;
  formErrorEl.textContent = problem.message;
  const target = field(problem.field);
  if (!target) return;
  if (typeof target.setAttribute === "function") target.setAttribute("aria-invalid", "true");
  const advanced = field("f-advanced");
  if (typeof advanced.contains === "function" && advanced.contains(target)) advanced.open = true;
  const focusable = problem.field === "f-days" ? field("f-day-0") : target;
  if (typeof focusable.focus === "function") focusable.focus();
  if (typeof formErrorEl.scrollIntoView === "function") formErrorEl.scrollIntoView({ block: "nearest" });
}

function renderCategoryChips(container, selected, onPick) {
  if (!container) return;
  container.innerHTML = "";
  CATEGORIES.forEach(function (cat) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "category-chip" + (selected === cat.id ? " is-selected" : "");
    if (btn.style && typeof btn.style.setProperty === "function") btn.style.setProperty("--chip-color", cat.color);
    else if (btn.style) btn.style.borderLeftColor = cat.color;
    btn.textContent = cat.label;
    btn.title = cat.label + " · " + KIND_LABEL[cat.kind];
    btn.dataset.category = cat.id;
    if (typeof btn.setAttribute === "function") btn.setAttribute("aria-pressed", String(selected === cat.id));
    btn.addEventListener("click", function () { onPick(cat.id); });
    container.appendChild(btn);
  });
}

function typeHint(category) {
  const type = categoryById(category);
  if (!type) return "";
  return type.kind === "locked"
    ? type.label + " is a fixed time. Drag on the calendar where it happens, or click for a 1-hour block."
    : type.label + " is flexible. Drag on a day you can work on it, about as long as it takes. Solve picks the exact time.";
}

function renderTypeChips() {
  renderCategoryChips(field("type-chips"), addType, function (category) {
    addType = category;
    renderTypeChips();
  });
  field("type-hint").textContent = typeHint(addType);
}

function pickDialogCategory(category) {
  const type = categoryById(category);
  field("f-category").value = category;
  if (!editingExisting && type && type.kind !== selectedKind()) setKind(type.kind);
  syncEditor();
}

/** Switch a new draft between fixed and flexible, carrying its length across. */
function setKind(kind) {
  const draft = readDraft();
  if (kind === "flexible") {
    fillDurationSelect(draft.endMin - draft.startMin);
    field("f-duration").value = String(draft.endMin - draft.startMin);
  } else {
    endEl.value = formatMinute(Math.min(DAY_END_MIN, draft.startMin + draft.duration_min));
  }
  field("f-kind-locked").checked = kind === "locked";
  field("f-kind-flexible").checked = kind === "flexible";
}

function setEditScope(scope) {
  editingScope = scope === "occurrence" ? "occurrence" : "series";
  field("f-scope-occurrence").checked = editingScope === "occurrence";
  field("f-scope-series").checked = editingScope === "series";
  formDeleteEl.textContent = editingScope === "occurrence" && editingOccurrenceDay !== null ? "Remove this day" : "Delete";
}

function openEditor(draft, block, occurrenceDay = null, scope = null) {
  if (!account || saving) return false;
  editingExisting = Boolean(block);
  editingOccurrenceDay = Number.isInteger(occurrenceDay) ? occurrenceDay : null;
  flexDaysTouched = editingExisting || draft.days.length < 7;
  showFormError(null);
  writeDraft(draft);
  const type = categoryById(draft.category);
  formHeadingEl.textContent = editingExisting ? "Edit " + block.title : "Add " + (type ? type.label : "to your week");
  field("form-save").textContent = editingExisting ? "Save changes" : "Add to week";
  formDeleteEl.hidden = !editingExisting;
  const canChangeMissed = editingExisting && block.kind === "locked" && editingOccurrenceDay !== null;
  formMissedEl.hidden = !canChangeMissed || (!(block.missed_days || []).includes(editingOccurrenceDay) && !weekState().trace);
  if (canChangeMissed) {
    const isMissed = (block.missed_days || []).includes(editingOccurrenceDay);
    formMissedEl.textContent = isMissed ? "Restore " + DAYS[editingOccurrenceDay] : "Mark " + DAYS[editingOccurrenceDay] + " missed";
    formMissedEl.className = isMissed ? "secondary" : "danger";
  }
  const showScope = editingExisting && block.kind === "locked" && isSeries(block) && editingOccurrenceDay !== null;
  field("edit-scope").hidden = !showScope;
  setEditScope(showScope && scope !== "series" ? "occurrence" : "series");
  field("f-advanced").open = false;
  syncEditor();
  if (typeof blockDialogEl.showModal === "function") {
    if (!blockDialogEl.open) blockDialogEl.showModal();
  } else {
    blockDialogEl.open = true;
  }
  field("f-title").focus();
  return true;
}

function openCreateDialog(day, startMin, endMin) {
  return openEditor(newDraft(addType, day, startMin, endMin), null);
}

function openBlockEditor(block, occurrenceDay = null, scope = null) {
  return openEditor(draftFromBlock(block, occurrenceDay), block, occurrenceDay, scope);
}

function closeForm() {
  if (blockDialogEl.open && typeof blockDialogEl.close === "function") blockDialogEl.close();
  blockDialogEl.open = false;
  editingOccurrenceDay = null;
  editingScope = "series";
  editingExisting = false;
  showFormError(null);
}

function applyDraft(draft) {
  const patch = draftPatch(draft);
  const id = draft.id || newId();
  const blocks = weekState().blocks;
  const existing = blocks.findIndex(function (item) { return item.id === id; });
  const prior = existing >= 0 ? blocks[existing] : null;
  if (draft.kind === "flexible") {
    if (patch.completed && prior) {
      const placed = weekState().trace?.placed.find(item => item.id === id) || prior;
      const completedDay = Number.isInteger(placed.completed_day)
        ? placed.completed_day
        : (placed.days.length === 1 ? placed.days[0] : null);
      if (placed.start && completedDay !== null && patch.days.includes(completedDay)) {
        patch.start = placed.start;
        patch.completed_day = completedDay;
      }
    } else {
      patch.completed_day = null;
    }
  }

  if (prior && draft.kind === "locked" && isSeries(prior) && editingScope === "occurrence" && editingOccurrenceDay !== null) {
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
      ...(prior || {}),
      id: id,
      kind: draft.kind,
      missed_days: draft.kind === "locked" && prior ? (prior.missed_days || []).filter(function (day) {
        return patch.days.includes(day);
      }) : [],
      ...patch,
    };
    if (existing >= 0) blocks[existing] = block;
    else blocks.push(block);
  }
}

formEl.addEventListener("submit", function (event) {
  event.preventDefault();
  if (!account || saving) return false;
  const draft = readDraft();
  const problem = draftProblem(draft);
  if (problem) {
    showFormError(problem);
    return false;
  }
  applyDraft(draft);
  closeForm();
  commitWeek();
  return true;
});

field("form-cancel").addEventListener("click", closeForm);
blockDialogEl.addEventListener("cancel", closeForm);

formMissedEl.addEventListener("click", async function () {
  if (!account || saving || editingOccurrenceDay === null) return;
  const id = field("f-id").value;
  const block = weekState().blocks.find(function (item) { return item.id === id; });
  if (!block || block.kind !== "locked") return;
  const day = editingOccurrenceDay;
  if (!(block.missed_days || []).includes(day)) {
    await recoverMissedOccurrence(id, day);
    return;
  }
  block.missed_days = block.missed_days.filter(function (missed) { return missed !== day; });
  closeForm();
  await commitWeek();
});

formDeleteEl.addEventListener("click", function () {
  if (!account || saving) return;
  const id = field("f-id").value;
  const prior = weekState().blocks.find(function (item) { return item.id === id; });
  if (prior && isSeries(prior) && editingScope === "occurrence" && editingOccurrenceDay !== null) {
    deleteOccurrenceById(id, editingOccurrenceDay);
    return;
  }
  deleteBlockById(id);
});

field("add-block").addEventListener("click", function () {
  openEditor(presetDraft(addType, selectedWeek), null);
});

["f-kind-locked", "f-kind-flexible"].forEach(function (id) {
  field(id).addEventListener("change", function () {
    setKind(field(id).value);
    syncEditor();
  });
});
["f-scope-occurrence", "f-scope-series"].forEach(function (id) {
  field(id).addEventListener("change", function () {
    setEditScope(selectedEditScope());
    syncEditor();
  });
});
field("f-when-day").addEventListener("change", function () {
  // A one-day block moves to the new day; a repeating block gains the day instead.
  const days = selectedDays();
  if (days.length === 1) field("f-day-" + days[0]).checked = false;
  syncEditor();
});
field("f-due-day").addEventListener("change", function () {
  if (!flexDaysTouched) {
    const due = field("f-due-day").value;
    setSelectedDays(daysThrough(due === "" ? null : Number(due)));
  }
  syncEditor();
});
DAYS.forEach(function (_name, day) {
  field("f-day-" + day).addEventListener("change", function () {
    flexDaysTouched = true;
    syncEditor();
  });
});
["f-duration", "f-due-time", "f-start", "f-end"].forEach(function (id) {
  field(id).addEventListener("change", syncEditor);
});

fillEditorSelects();
renderTypeChips();
