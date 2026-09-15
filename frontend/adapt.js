// Stage 4 plan adaptations shared by the browser and desktop app.

let spreadAssignmentId = null;
let spreadBusy = false;

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
  closeAdaptDialog(document.getElementById("spread-dialog"));
  showSpreadError("");
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
