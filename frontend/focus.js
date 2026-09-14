/** Daily Scheduler's one-line Now / Next status. Empty when nothing is on now or later today. */
function nowNextLine(result, minute) {
  const parts = [];
  if (result.current) {
    const end = parseStart(result.current.start) + result.current.duration_min;
    parts.push("Now: " + result.current.title + " · " + formatDuration(end - minute) + " left");
  }
  if (result.next) {
    const wait = parseStart(result.next.start) - minute;
    parts.push("Next: " + result.next.title + " at " + result.next.start + (result.current ? "" : " (in " + formatDuration(wait) + ")"));
  }
  return parts.join("  →  ");
}

// Quick focus needs no task, so the section is there whenever someone is signed in.
function syncFocusSection() {
  document.getElementById("focus-section").hidden = !account;
}

function updateLiveDisplay(nowDate) {
  const target = document.getElementById("now-next");
  if (!target) return;
  const now = nowDate || new Date();
  const info = currentDateInfo(now);
  const state = weeks.get(info.week);
  const status = nowNextLine(nowAndNext(scheduledBlocksForState(state), info.day, info.minute), info.minute);
  target.textContent = status;
  target.hidden = !status;
  document.querySelectorAll(".current-time-line").forEach(function (line) {
    if (typeof line.remove === "function") line.remove();
    else line.hidden = true;
  });
  if (selectedWeek !== info.week || info.minute < DAY_START_MIN || info.minute >= DAY_END_MIN) return;
  const lane = Array.from(weekEl.children).find(function (child) {
    return child.classList && child.classList.contains("day-lane") && Number(child.dataset.day) === info.day;
  });
  if (!lane) return;
  const line = document.createElement("div");
  line.className = "current-time-line";
  line.style.top = ((info.minute - DAY_START_MIN) / 60) * hourHeightRem() + "rem";
  line.title = "Current time " + formatMinute(info.minute);
  lane.appendChild(line);
}

function phaseDurationMs(phase) {
  const minutes = phase === "work" ? prefs.timer_work_min :
    (phase === "long_break" ? prefs.timer_long_break_min : prefs.timer_break_min);
  return minutes * 60000;
}

function formatCountdown(milliseconds) {
  const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
  return String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
}

const MAX_ESTIMATE_MIN = 7140;
const MORE_TIME_CHOICES = [15, 30, 45, 60, 90, 120, 180, 240];
const FOCUS_STORAGE_PREFIX = "flexweek.focus.";
const FOCUS_PHASES = ["work", "break", "long_break", "ended"];
const FOCUS_PHASE_LABEL = { work: "Focus session", break: "Break", long_break: "Long break", ended: "Session done" };
// After a homework session ends, whether the student is choosing how much more time it needs.
let focusAskingMore = false;

function renderFocusPanel(nowMs) {
  const panel = document.getElementById("focus-panel");
  if (!panel) return;
  panel.hidden = !focusState;
  syncFocusSection();
  if (!focusState) return;
  const ended = focusState.phase === "ended";
  document.getElementById("focus-task").textContent = focusState.title;
  document.getElementById("focus-phase").textContent = FOCUS_PHASE_LABEL[focusState.phase];
  const left = focusState.running ? focusState.endsAt - (nowMs || Date.now()) : focusState.remainingMs;
  document.getElementById("focus-time").textContent = formatCountdown(left);
  document.getElementById("focus-pause").textContent = focusState.running ? "Pause" : "Resume";
  document.getElementById("focus-controls").hidden = ended;
  document.getElementById("focus-choices").hidden = !ended || focusAskingMore;
  document.getElementById("focus-more-form").hidden = !ended || !focusAskingMore;
}

function resetFocusTimer(hide) {
  if (focusTimer) clearInterval(focusTimer);
  focusTimer = null;
  focusState = null;
  focusAskingMore = false;
  const panel = document.getElementById("focus-panel");
  if (panel && hide !== false) panel.hidden = true;
  syncFocusSection();
  persistFocus();
}

/** The timer outlives a reload in sessionStorage, as ids and times only; titles come back after sign-in. */
function persistFocus() {
  if (!account) return;
  try {
    const key = FOCUS_STORAGE_PREFIX + account.id;
    if (!focusState) {
      sessionStorage.removeItem(key);
      return;
    }
    sessionStorage.setItem(key, JSON.stringify({
      assignmentId: focusState.assignmentId, sessionId: focusState.blockId, weekStart: focusState.weekStart,
      day: focusState.day, start: focusState.start, phase: focusState.phase, cycles: focusState.cycles,
      endsAt: focusState.running ? focusState.endsAt : null,
      remainingMs: focusState.running ? null : focusState.remainingMs,
    }));
  } catch { /* Without sessionStorage the timer still runs until the page closes. */ }
}

function forgetFocus(accountId) {
  try { sessionStorage.removeItem(FOCUS_STORAGE_PREFIX + accountId); } catch { /* Nothing was stored. */ }
}

/** After sign-in, resume this account's timer from before a reload, and drop any other account's. */
function restoreFocus() {
  let saved = null;
  try {
    const mine = FOCUS_STORAGE_PREFIX + account.id;
    for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = sessionStorage.key(index);
      if (key && key.startsWith(FOCUS_STORAGE_PREFIX) && key !== mine) sessionStorage.removeItem(key);
    }
    saved = JSON.parse(sessionStorage.getItem(mine) || "null");
  } catch { return; }
  if (focusState || !saved) return;
  const assignment = typeof saved.assignmentId === "string" ? assignments.get(saved.assignmentId) : null;
  const valid = FOCUS_PHASES.includes(saved.phase) && isWeekStart(saved.weekStart) && Number.isInteger(saved.cycles) &&
    (typeof saved.endsAt === "number" || typeof saved.remainingMs === "number");
  // Homework finished or deleted since then has nothing left to time.
  if (!valid || (saved.assignmentId && (!assignment || assignment.completed))) {
    forgetFocus(account.id);
    return;
  }
  const sessionId = typeof saved.sessionId === "string" ? saved.sessionId : null;
  const week = weeks.get(saved.weekStart);
  const block = sessionId && week ? week.blocks.find(function (item) { return item.id === sessionId; }) : null;
  focusState = {
    weekStart: saved.weekStart, blockId: sessionId, assignmentId: assignment ? assignment.id : null,
    day: Number.isInteger(saved.day) ? saved.day : null, start: typeof saved.start === "string" ? saved.start : null,
    title: sessionId ? (assignment || block || { title: "Focus session" }).title : "Quick focus",
    phase: saved.phase, cycles: saved.cycles, running: typeof saved.endsAt === "number",
    endsAt: saved.endsAt || 0, remainingMs: saved.remainingMs || 0,
  };
  startFocusInterval();
  if (focusState.running && focusState.endsAt <= Date.now()) {
    focusState.running = false;
    focusState.remainingMs = 0;
    if (focusState.phase === "work") {
      // It ran out while the page was closed: count it now and ask what comes next.
      advanceFocusPhase(true);
    } else {
      focusState.phase = "work";
      focusState.remainingMs = phaseDurationMs("work");
      setStatus("The break ended while FlexWeek was closed. Press Resume to focus again.");
    }
  }
  renderFocusPanel();
  persistFocus();
}

function resolveFocusPlacement(blockId, day) {
  const state = weekState();
  const source = state.blocks.find(function (block) { return block.id === blockId; });
  if (!source) return null;
  const placed = source.start ? source : state.trace && state.trace.placed.find(function (block) {
    return block.id === blockId && (day === undefined || block.days.indexOf(day) !== -1);
  });
  return placed && placed.start ? { source: source, placed: placed, day: placed.days[0] } : null;
}

function startFocus(blockId, day) {
  if (!account || saving || focusBusy) return false;
  const found = resolveFocusPlacement(blockId, day);
  if (!found || found.source.completed || found.source.pomodoro_role === "break") {
    setStatus("Place an unfinished work block before starting focus.");
    return false;
  }
  return beginFocus({
    weekStart: selectedWeek, blockId: blockId, assignmentId: found.source.assignment_id || null,
    day: found.day, start: found.placed.start, title: found.source.title,
  });
}

/** Quick focus times work that is not on the calendar, so it credits nothing. */
function startQuickFocus() {
  if (!account || saving || focusBusy) return false;
  return beginFocus({ weekStart: selectedWeek, blockId: null, assignmentId: null, day: null, start: null, title: "Quick focus" });
}

function beginFocus(target) {
  if (focusState && !confirm("Stop the timer for " + focusState.title + " and start " + target.title + " instead?")) {
    return false;
  }
  resetFocusTimer();
  focusState = {
    ...target, phase: "work", cycles: 0, running: true,
    remainingMs: phaseDurationMs("work"), endsAt: Date.now() + phaseDurationMs("work"),
  };
  startFocusInterval();
  renderFocusPanel();
  persistFocus();
  return true;
}

function startFocusInterval() {
  if (focusTimer) clearInterval(focusTimer);
  focusTimer = setInterval(function () { focusTick(); }, 500);
  if (focusTimer && typeof focusTimer.unref === "function") focusTimer.unref();
}

async function creditFocusSession() {
  // Quick focus has no task, so it credits nothing.
  if (!focusState || !focusState.blockId) return;
  if (focusState.assignmentId) {
    // Minutes count toward the assignment and never finish anything; that is the student's choice.
    const assignment = assignments.get(focusState.assignmentId);
    // A session's own focus fields must stay 0, so without its assignment there is nowhere to credit.
    if (!assignment) {
      setStatus("This homework did not load, so the focus time was not counted. Reload the week and try again.");
      return;
    }
    putAssignment({
      ...assignment,
      focus_sessions: Math.min(9999, (assignment.focus_sessions || 0) + 1),
      focus_minutes: Math.min(71400, (assignment.focus_minutes || 0) + prefs.timer_work_min),
    });
  } else {
    if (focusState.weekStart !== selectedWeek) return;
    const block = weekState().blocks.find(function (item) { return item.id === focusState.blockId; });
    if (!block) return;
    block.focus_sessions = Math.min(9999, (block.focus_sessions || 0) + 1);
    block.focus_minutes = Math.min(71400, (block.focus_minutes || 0) + prefs.timer_work_min);
  }
  // Focus credit is progress, not an edit, so Undo leaves it alone.
  absorbIntoHistory();
  await saveWeek();
  renderWeek();
}

async function advanceFocusPhase(completed) {
  if (!focusState || focusBusy || focusState.phase === "ended") return;
  focusBusy = true;
  try {
    if (focusState.phase === "work") {
      if (completed) await creditFocusSession();
      if (!focusState) return;
      focusState.cycles += completed ? 1 : 0;
      if (completed && focusState.assignmentId && assignments.has(focusState.assignmentId)) {
        // Homework asks what comes next instead of rolling into a break.
        focusState.phase = "ended";
        focusState.running = false;
        focusState.remainingMs = 0;
        maybeNotify("Focus session done", focusState.title, true, "soft");
        renderFocusPanel();
        persistFocus();
        return;
      }
      beginFocusBreak();
    } else {
      setFocusPhase("work");
    }
  } finally {
    focusBusy = false;
  }
}

function setFocusPhase(phase) {
  focusAskingMore = false;
  focusState.phase = phase;
  focusState.running = true;
  focusState.remainingMs = phaseDurationMs(phase);
  focusState.endsAt = Date.now() + focusState.remainingMs;
  maybeNotify(FOCUS_PHASE_LABEL[phase], focusState.title, true, phase === "work" ? "bright" : "soft");
  renderFocusPanel();
  persistFocus();
}

function beginFocusBreak() {
  setFocusPhase(focusState.cycles > 0 && focusState.cycles % prefs.timer_long_break_every === 0 ? "long_break" : "break");
}

/** Finished: the homework is done and the session keeps the slot it was worked in, saved together. */
async function finishFocusedHomework() {
  if (!focusState || focusState.phase !== "ended" || saving || focusBusy) return false;
  const target = focusState;
  if (selectedWeek !== target.weekStart && !await selectWeek(target.weekStart)) return false;
  const assignment = assignments.get(target.assignmentId);
  if (!assignment || focusState !== target) return false;
  const block = weekState().blocks.find(function (item) { return item.id === target.blockId; });
  if (block) {
    block.completed = true;
    if (block.kind === "flexible") {
      if (target.start && Number.isInteger(target.day) && block.days.includes(target.day)) {
        block.start = target.start;
        block.completed_day = target.day;
      } else if (!Number.isInteger(block.completed_day)) {
        block.start = null;
      }
    }
  }
  putAssignment({ ...assignment, completed: true, completed_at: localStamp() });
  resetFocusTimer();
  commitWeek("Finished " + assignment.title + ".", "finishing " + assignment.title);
  return true;
}

function moreTimeChoices(assignment) {
  return MORE_TIME_CHOICES.filter(function (minutes) { return assignment.estimate_min + minutes <= MAX_ESTIMATE_MIN; });
}

/** Need more time: add minutes on the 15-minute grid to the homework's total, then take the break. */
async function addFocusTime(minutes) {
  if (!focusState || focusState.phase !== "ended" || saving || focusBusy) return false;
  const assignment = assignments.get(focusState.assignmentId);
  if (!assignment || !moreTimeChoices(assignment).includes(minutes)) {
    setStatus("Choose how much more time it needs.");
    return false;
  }
  putAssignment({ ...assignment, estimate_min: assignment.estimate_min + minutes });
  recordStep("adding time to " + assignment.title);
  beginFocusBreak();
  const saved = await saveWeek();
  renderWeek();
  if (saved) {
    setStatus("Added " + formatDuration(minutes) + " to " + assignment.title + ". Plan it under Continuing, then press Solve.");
  }
  return saved;
}

function takeFocusBreak() {
  if (!focusState || focusState.phase !== "ended" || focusBusy) return false;
  beginFocusBreak();
  return true;
}

function focusTick(nowMs) {
  if (!focusState || !focusState.running) return;
  const now = nowMs || Date.now();
  if (focusState.endsAt <= now) {
    focusState.running = false;
    focusState.remainingMs = 0;
    advanceFocusPhase(true);
  }
  renderFocusPanel(now);
}

function toggleFocusPause() {
  if (!focusState || focusBusy || saving || focusState.phase === "ended") return;
  if (focusState.running) {
    focusState.remainingMs = Math.max(0, focusState.endsAt - Date.now());
    focusState.running = false;
  } else {
    focusState.running = true;
    focusState.endsAt = Date.now() + focusState.remainingMs;
  }
  renderFocusPanel();
  persistFocus();
}

function renderFocusTasks() {
  const list = document.getElementById("focus-tasks");
  if (!list) return;
  list.replaceChildren();
  const scheduled = scheduledBlocksForState(weekState());
  const placementById = new Map(scheduled.map(function (block) { return [block.id, block]; }));
  // Only work that has a time and is not done can be focused; school and breaks cannot.
  weekState().blocks.filter(function (block) {
    return (block.kind === "flexible" || block.pomodoro_role === "work") && !block.completed &&
      !(assignmentOf(block) || {}).completed && placementById.has(block.id);
  }).forEach(function (block) {
    const placement = placementById.get(block.id);
    const progress = assignmentOf(block) || block;
    const item = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = block.title;
    const count = document.createElement("small");
    count.textContent = DAYS[placement.days[0]] + " " + placement.start + (progress.focus_sessions
      ? " · " + progress.focus_sessions + (progress.focus_sessions === 1 ? " session, " : " sessions, ") + formatDuration(progress.focus_minutes || 0)
      : "");
    const start = document.createElement("button");
    start.type = "button";
    start.textContent = "Start";
    start.addEventListener("click", function () {
      const placed = placementById.get(block.id);
      startFocus(block.id, placed && placed.days[0]);
    });
    item.appendChild(name);
    item.appendChild(count);
    item.appendChild(start);
    list.appendChild(item);
  });
  syncFocusSection();
}

document.getElementById("focus-pause").addEventListener("click", toggleFocusPause);
document.getElementById("focus-skip").addEventListener("click", function () {
  if (saving || focusBusy) return;
  advanceFocusPhase(false);
});
document.getElementById("focus-reset").addEventListener("click", function () { resetFocusTimer(); });
document.getElementById("focus-quick").addEventListener("click", function () { startQuickFocus(); });
document.getElementById("focus-finished").addEventListener("click", function () { finishFocusedHomework(); });
document.getElementById("focus-break").addEventListener("click", function () { takeFocusBreak(); });
document.getElementById("focus-more").addEventListener("click", function () {
  const assignment = focusState && assignments.get(focusState.assignmentId);
  const choices = assignment ? moreTimeChoices(assignment) : [];
  if (!choices.length) {
    setStatus("This homework already has the most time FlexWeek allows.");
    return;
  }
  const select = document.getElementById("focus-more-min");
  fillOptions(select, choices.map(function (minutes) { return [minutes, formatDuration(minutes)]; }));
  select.value = String(choices[Math.min(1, choices.length - 1)]);
  focusAskingMore = true;
  renderFocusPanel();
});
document.getElementById("focus-more-add").addEventListener("click", function () {
  addFocusTime(Number(document.getElementById("focus-more-min").value));
});
document.getElementById("focus-more-cancel").addEventListener("click", function () {
  focusAskingMore = false;
  renderFocusPanel();
});
