function updateLiveDisplay(nowDate) {
  const target = document.getElementById("now-next");
  if (!target) return;
  const now = nowDate || new Date();
  const info = currentDateInfo(now);
  const state = weeks.get(info.week);
  const result = nowAndNext(scheduledBlocksForState(state), info.day, info.minute);
  const currentText = result.current ? "Now: " + result.current.title + " until " +
    formatMinute(parseStart(result.current.start) + result.current.duration_min) : "Now: Free";
  const nextText = result.next ? "Next: " + result.next.title + " at " + result.next.start : "Next: Nothing scheduled";
  target.textContent = currentText + "\n" + nextText;
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

function renderFocusPanel(nowMs) {
  const panel = document.getElementById("focus-panel");
  if (!panel) return;
  panel.hidden = !focusState;
  if (!focusState) return;
  document.getElementById("focus-task").textContent = focusState.title;
  document.getElementById("focus-phase").textContent = focusState.phase === "work" ? "Focus session" :
    (focusState.phase === "long_break" ? "Long break" : "Break");
  const left = focusState.running ? focusState.endsAt - (nowMs || Date.now()) : focusState.remainingMs;
  document.getElementById("focus-time").textContent = formatCountdown(left);
  document.getElementById("focus-pause").textContent = focusState.running ? "Pause" : "Resume";
}

function resetFocusTimer(hide) {
  if (focusTimer) clearInterval(focusTimer);
  focusTimer = null;
  focusState = null;
  const panel = document.getElementById("focus-panel");
  if (panel && hide !== false) panel.hidden = true;
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
  resetFocusTimer();
  focusState = {
    weekStart: selectedWeek,
    blockId: blockId,
    day: found.day,
    start: found.placed.start,
    title: found.source.title,
    phase: "work",
    cycles: 0,
    running: true,
    remainingMs: phaseDurationMs("work"),
    endsAt: Date.now() + phaseDurationMs("work"),
  };
  renderFocusPanel();
  focusTimer = setInterval(function () { focusTick(); }, 500);
  if (focusTimer && typeof focusTimer.unref === "function") focusTimer.unref();
  return true;
}

async function creditFocusSession() {
  if (!focusState || focusState.weekStart !== selectedWeek) return;
  const block = weekState().blocks.find(function (item) { return item.id === focusState.blockId; });
  if (!block) return;
  block.focus_sessions = Math.min(9999, (block.focus_sessions || 0) + 1);
  block.focus_minutes = Math.min(71400, (block.focus_minutes || 0) + prefs.timer_work_min);
  if (block.focus_minutes >= block.duration_min) {
    block.completed = true;
    if (block.kind === "flexible") {
      block.start = focusState.start;
      block.completed_day = focusState.day;
    }
  }
  await saveWeek();
  renderWeek();
}

async function advanceFocusPhase(completed) {
  if (!focusState || focusBusy) return;
  focusBusy = true;
  try {
    const oldPhase = focusState.phase;
    if (oldPhase === "work") {
      if (completed) await creditFocusSession();
      if (!focusState) return;
      focusState.cycles += completed ? 1 : 0;
      focusState.phase = focusState.cycles > 0 && focusState.cycles % prefs.timer_long_break_every === 0
        ? "long_break" : "break";
    } else {
      focusState.phase = "work";
    }
    focusState.running = true;
    focusState.remainingMs = phaseDurationMs(focusState.phase);
    focusState.endsAt = Date.now() + focusState.remainingMs;
    const label = focusState.phase === "work" ? "Focus session" :
      (focusState.phase === "long_break" ? "Long break" : "Break");
    maybeNotify(label, focusState.title, true, focusState.phase === "work" ? "bright" : "soft");
    renderFocusPanel();
  } finally {
    focusBusy = false;
  }
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
  if (!focusState || focusBusy || saving) return;
  if (focusState.running) {
    focusState.remainingMs = Math.max(0, focusState.endsAt - Date.now());
    focusState.running = false;
  } else {
    focusState.running = true;
    focusState.endsAt = Date.now() + focusState.remainingMs;
  }
  renderFocusPanel();
}

function renderFocusTasks() {
  const list = document.getElementById("focus-tasks");
  if (!list) return;
  list.replaceChildren();
  const scheduled = scheduledBlocksForState(weekState());
  const placementById = new Map(scheduled.map(function (block) { return [block.id, block]; }));
  weekState().blocks.filter(function (block) {
    return block.pomodoro_role !== "break";
  }).forEach(function (block) {
    const item = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = block.title;
    const count = document.createElement("small");
    count.textContent = (block.focus_sessions || 0) + " sessions · " + (block.focus_minutes || 0) + " min";
    const start = document.createElement("button");
    start.type = "button";
    start.textContent = "Focus";
    start.disabled = block.completed || !placementById.has(block.id);
    start.addEventListener("click", function () {
      const placed = placementById.get(block.id);
      startFocus(block.id, placed && placed.days[0]);
    });
    item.appendChild(name);
    item.appendChild(count);
    item.appendChild(start);
    list.appendChild(item);
  });
}

document.getElementById("focus-pause").addEventListener("click", toggleFocusPause);
document.getElementById("focus-skip").addEventListener("click", function () {
  if (saving || focusBusy) return;
  advanceFocusPhase(false);
});
document.getElementById("focus-reset").addEventListener("click", function () { resetFocusTimer(); });
