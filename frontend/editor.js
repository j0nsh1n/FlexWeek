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
  document.getElementById("f-spotify").value = editing && block.spotify_url ? block.spotify_url : "";
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
  const spotify = document.getElementById("f-spotify").value.trim();
  if (spotify && !safeSpotifyUrl(spotify)) {
    showFormError("Use an https://open.spotify.com share link.");
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
    spotify_url: spotify || null,
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
      ...(prior || {}),
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

formEl.querySelectorAll('input[name="f-scope"]').forEach(function (el) {
  el.addEventListener("change", function () {
    setEditScope(selectedEditScope());
    formDeleteEl.textContent = selectedEditScope() === "occurrence" ? "Remove this day" : "Delete";
  });
});

fillTimeSelect(startEl, false);
fillTimeSelect(dueTimeEl, true);
ensureCategoryOptions();
