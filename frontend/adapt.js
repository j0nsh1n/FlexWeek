// Stage 4 plan adaptations shared by the browser and desktop app.

let spreadAssignmentId = null;
let spreadBusy = false;
let latePreview = null;
let lateBusy = false;

function openAdaptDialog(dialog) {
  if (typeof dialog.showModal === "function") {
    if (!dialog.open) dialog.showModal();
  } else {
    dialog.open = true;
  }
}

function closeAdaptDialog(dialog) {
  if (dialog.open && typeof dialog.close === "function") dialog.close();
  dialog.open = false;
}

function showSpreadError(message) {
  const error = document.getElementById("spread-error");
  error.textContent = message || "";
  error.hidden = !message;
}

function spreadSessionChoices(selected) {
  const select = document.getElementById("spread-session");
  select.replaceChildren();
  for (let minutes = SNAP_MIN; minutes <= 180; minutes += SNAP_MIN) {
    const option = document.createElement("option");
    option.value = String(minutes);
    option.textContent = formatDuration(minutes);
    select.appendChild(option);
  }
  select.value = String(selected);
}

function openSpreadDialog(assignmentId) {
  if (!account || saving || spreadBusy) return false;
  const item = assignments.get(assignmentId);
  if (!item || item.completed) return false;
  spreadAssignmentId = item.id;
  const dueDate = item.due.slice(0, 10);
  const baseDate = selectedDay && selectedDay > todayIso() ? selectedDay : todayIso();
  const fromDate = baseDate <= dueDate ? baseDate : dueDate;
  const gridRemaining = Math.floor(Math.max(SNAP_MIN, item.unplanned_min || SNAP_MIN) / SNAP_MIN) * SNAP_MIN;
  spreadSessionChoices(Math.min(60, gridRemaining, 180));
  const from = document.getElementById("spread-from");
  from.max = dueDate;
  from.value = fromDate;
  document.getElementById("spread-heading").textContent = "Spread " + item.title;
  document.getElementById("spread-detail").textContent = formatDuration(item.estimate_min) + " total · "
    + formatDuration(item.focus_minutes || 0) + " focused · due " + dueLabel(item.due);
  showSpreadError("");
  closeHomeworkDialog();
  openAdaptDialog(document.getElementById("spread-dialog"));
  return true;
}

function validSpreadSession(session) {
  if (!session || !isWeekStart(session.week_start) || !/^\d{4}-\d{2}-\d{2}$/.test(session.date)
      || !Array.isArray(session.days) || session.days.length !== 1
      || !Number.isInteger(session.days[0]) || session.days[0] < 0 || session.days[0] > 6
      || dayOffset(session.week_start, session.date) !== session.days[0]
      || !Number.isInteger(session.duration_min) || session.duration_min < SNAP_MIN
      || session.duration_min > 180 || session.duration_min % SNAP_MIN) return false;
  return true;
}

function spreadPreviewRows(item, sessions) {
  return sessions.map(function (session, index) {
    const groupId = "spread-" + newId() + "-" + index.toString(36);
    const block = copiedHomeworkBlock({}, item, session.days[0], session.duration_min, groupId);
    return {
      weekStart: session.week_start,
      day: session.days[0],
      fixed: false,
      block: block,
      groupId: groupId,
      checked: true,
      invalid: "",
    };
  });
}

async function previewSpread() {
  if (!account || saving || spreadBusy || !spreadAssignmentId) return false;
  const item = assignments.get(spreadAssignmentId);
  if (!item || item.completed) return false;
  const sessionMin = Number(document.getElementById("spread-session").value);
  const fromDate = document.getElementById("spread-from").value;
  const dueDate = item.due.slice(0, 10);
  if (!Number.isInteger(sessionMin) || sessionMin < SNAP_MIN || sessionMin > 180 || sessionMin % SNAP_MIN) {
    showSpreadError("Choose a session length from 15 minutes through 3 hours.");
    return false;
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(fromDate) || !parseDate(fromDate) || fromDate > dueDate) {
    showSpreadError("Choose a start date on or before the due date.");
    return false;
  }
  const spreadEpoch = epoch;
  const accountId = account.id;
  spreadBusy = true;
  document.getElementById("spread-preview").disabled = true;
  showSpreadError("");
  try {
    const result = await api("/api/assignments/" + encodeURIComponent(item.id) + "/spread", {
      method: "POST", body: JSON.stringify({ session_min: sessionMin, from_date: fromDate }),
    });
    if (spreadEpoch !== epoch || !account || account.id !== accountId) return false;
    if (result.assignment_id !== item.id || !Array.isArray(result.sessions)
        || !Number.isInteger(result.remaining_min) || result.remaining_min < 0
        || result.sessions.some(function (session) { return !validSpreadSession(session); })) {
      throw new Error("The session preview was invalid. Nothing was changed.");
    }
    if (!result.sessions.length) {
      showSpreadError(result.remaining_min
        ? result.remaining_min + " minutes remain, but they do not fit the 15-minute planning grid."
        : "All of this homework is already focused or planned.");
      return false;
    }
    const total = result.sessions.reduce(function (sum, session) { return sum + session.duration_min; }, 0);
    let summary = result.sessions.length + (result.sessions.length === 1 ? " session" : " sessions")
      + " · " + formatDuration(total) + " ready to add before " + dueLabel(item.due) + ".";
    if (result.remaining_min) {
      summary += " " + result.remaining_min
        + " minutes cannot fit the 15-minute grid and have not been dropped from the homework total.";
    }
    const rows = spreadPreviewRows(item, result.sessions);
    const opened = showStage3Preview("Spread " + item.title, summary, rows, {
      label: "spreading " + item.title,
      attemptKey: "spread|" + accountId + "|" + item.id + "|" + fromDate + "|" + sessionMin,
    });
    if (opened) closeAdaptDialog(document.getElementById("spread-dialog"));
    return opened;
  } catch (error) {
    if (spreadEpoch === epoch && account && account.id === accountId) showSpreadError(error.message);
    return false;
  } finally {
    if (spreadEpoch === epoch) {
      spreadBusy = false;
      document.getElementById("spread-preview").disabled = false;
    }
  }
}

function prepareAdaptAccount() {
  clearAdaptState();
}

function clearAdaptState() {
  spreadAssignmentId = null;
  spreadBusy = false;
  latePreview = null;
  lateBusy = false;
  closeAdaptDialog(document.getElementById("spread-dialog"));
  closeAdaptDialog(document.getElementById("late-dialog"));
  showSpreadError("");
  showLateError("");
}

function showLateError(message) {
  const error = document.getElementById("late-error");
  error.textContent = message || "";
  error.hidden = !message;
}

function lateStart(info) {
  return Math.floor(info.minute / SNAP_MIN) * SNAP_MIN;
}

function openRunningLate(now) {
  if (!account || saving || lateBusy) return false;
  const info = currentDateInfo(now);
  if (selectedWeek !== info.week) {
    setStatus("Open this week before using Running late.");
    return false;
  }
  if (info.minute < DAY_START_MIN || info.minute >= DAY_END_MIN) {
    setStatus("Running late is available between 06:00 and 23:00.");
    return false;
  }
  if (weekState().dirty || weekState().conflict) {
    setStatus("Save or reload this week before previewing a late start.");
    return false;
  }
  if (weekState().blocks.length >= MAX_IMPORT_BLOCKS) {
    setStatus("This week already has 100 blocks. Remove one before recording a late start.");
    return false;
  }
  latePreview = null;
  document.getElementById("late-preview").hidden = true;
  document.getElementById("late-accept").hidden = true;
  document.getElementById("late-minutes").disabled = false;
  document.getElementById("late-context").textContent = "Starting from " + formatMinute(lateStart(info))
    + " today (" + DAY_FULL[info.day] + ").";
  showLateError("");
  openAdaptDialog(document.getElementById("late-dialog"));
  return true;
}

function renderLatePreview(trace) {
  const changes = document.getElementById("late-changes");
  changes.replaceChildren();
  (trace.moves || []).forEach(function (move) {
    const item = document.createElement("li");
    const fromDay = Number.isInteger(move.from_day) ? DAY_FULL[move.from_day] + " " : "";
    const toDay = Number.isInteger(move.to_day) ? DAY_FULL[move.to_day] + " " : "";
    item.textContent = blockTitle(move.block_id) + ": " + fromDay + (move.from_start || "unscheduled")
      + " → " + toDay + (move.to_start || "unscheduled");
    changes.appendChild(item);
  });
  (trace.unplaced || []).forEach(function (block) {
    const item = document.createElement("li");
    item.textContent = block.title + " no longer fits and will stay on the task list.";
    changes.appendChild(item);
  });
  if (!changes.children.length) {
    const item = document.createElement("li");
    item.textContent = "No homework needs to move.";
    changes.appendChild(item);
  }
  const moved = (trace.moves || []).length;
  const unplaced = (trace.unplaced || []).length;
  document.getElementById("late-summary").textContent = moved + (moved === 1 ? " task moves" : " tasks move")
    + " · " + unplaced + (unplaced === 1 ? " task no longer fits" : " tasks no longer fit");
  document.getElementById("late-preview").hidden = false;
  document.getElementById("late-accept").hidden = false;
  document.getElementById("late-minutes").disabled = true;
}

async function previewRunningLate(now) {
  if (!account || saving || lateBusy) return false;
  const info = currentDateInfo(now);
  if (selectedWeek !== info.week || info.minute < DAY_START_MIN || info.minute >= DAY_END_MIN) return false;
  const state = weekState();
  if (state.dirty || state.conflict || state.blocks.length >= MAX_IMPORT_BLOCKS) return false;
  const minutes = Number(document.getElementById("late-minutes").value);
  if (![15, 30, 60].includes(minutes)) {
    showLateError("Choose 15, 30 or 60 minutes.");
    return false;
  }
  const fromMin = lateStart(info);
  const fromStart = formatMinute(fromMin);
  const lateEpoch = epoch;
  const accountId = account.id;
  const weekStart = selectedWeek;
  lateBusy = true;
  document.getElementById("late-preview-button").disabled = true;
  showLateError("");
  try {
    let previous = state.trace && state.trace.placed;
    if (!previous) {
      const base = await api("/api/solve", { method: "POST", body: JSON.stringify({
        week_start: weekStart, blocks: state.blocks,
      }) });
      previous = base.placed || [];
    }
    const trace = await api("/api/solve", { method: "POST", body: JSON.stringify({
      week_start: weekStart,
      blocks: state.blocks,
      running_late: { day: info.day, minutes: minutes, from_start: fromStart, previous_placed: previous },
    }) });
    if (lateEpoch !== epoch || !account || account.id !== accountId || selectedWeek !== weekStart) return false;
    if (!Array.isArray(trace.placed) || !Array.isArray(trace.unplaced) || !Array.isArray(trace.moves)) {
      throw new Error("The late-plan preview was invalid. Nothing was changed.");
    }
    const duration = Math.min(minutes, DAY_END_MIN - fromMin);
    const operationId = stage3OperationId();
    const stem = operationId.replace(/-/g, "").slice(0, 24);
    latePreview = {
      trace: trace,
      accountId: accountId,
      epoch: lateEpoch,
      weekStart: weekStart,
      operationId: operationId,
      block: {
        id: "b-late-" + stem,
        kind: "locked",
        title: "Running late",
        duration_min: duration,
        days: [info.day],
        start: fromStart,
        priority: 1,
        energy: "medium",
        category: "downtime",
        completed: false,
        missed_days: [],
      },
      stale: false,
    };
    renderLatePreview(trace);
    return true;
  } catch (error) {
    if (lateEpoch === epoch && account && account.id === accountId) showLateError(error.message);
    return false;
  } finally {
    if (lateEpoch === epoch) {
      lateBusy = false;
      document.getElementById("late-preview-button").disabled = false;
    }
  }
}

async function acceptRunningLate() {
  if (!latePreview || latePreview.stale || lateBusy || saving || !account
      || epoch !== latePreview.epoch || account.id !== latePreview.accountId
      || selectedWeek !== latePreview.weekStart) return false;
  const active = latePreview;
  const acceptEpoch = epoch;
  lateBusy = true;
  saving = true;
  lockEditor(true);
  document.getElementById("late-accept").disabled = true;
  showLateError("");
  let saved = false;
  try {
    await saveStage3Blocks([{ weekStart: active.weekStart, block: active.block }], {
      operationId: active.operationId,
      label: "running late",
      recoveryLabel: null,
    });
    if (acceptEpoch !== epoch) return false;
    saved = true;
    closeAdaptDialog(document.getElementById("late-dialog"));
    latePreview = null;
    clearSolveResult();
    renderWeekNav();
    renderWeek();
    refreshDayData();
  } catch (error) {
    if (acceptEpoch === epoch) {
      if (error.status === 409) {
        active.stale = true;
        showLateError("This week changed elsewhere. Reload it before accepting this preview.");
      } else {
        showLateError(error.message);
      }
    }
  } finally {
    if (acceptEpoch === epoch) {
      saving = false;
      lateBusy = false;
      lockEditor(false);
      document.getElementById("late-accept").disabled = Boolean(active.stale);
    }
  }
  if (saved && acceptEpoch === epoch) {
    const planned = await solveWeek();
    if (planned && acceptEpoch === epoch) {
      setStatus("Saved the late start and updated your plan. Undo removes the late time.");
    }
  }
  return saved;
}

document.getElementById("hw-spread").addEventListener("click", function () {
  if (homeworkEditingId) openSpreadDialog(homeworkEditingId);
});
document.getElementById("spread-form").addEventListener("submit", function (event) {
  event.preventDefault();
  previewSpread();
});
document.getElementById("spread-cancel").addEventListener("click", function () {
  if (spreadBusy) return;
  spreadAssignmentId = null;
  closeAdaptDialog(document.getElementById("spread-dialog"));
});
document.getElementById("running-late").addEventListener("click", openRunningLate);
document.getElementById("late-form").addEventListener("submit", function (event) {
  event.preventDefault();
  previewRunningLate();
});
document.getElementById("late-accept").addEventListener("click", acceptRunningLate);
document.getElementById("late-cancel").addEventListener("click", function () {
  if (lateBusy) return;
  latePreview = null;
  closeAdaptDialog(document.getElementById("late-dialog"));
});
