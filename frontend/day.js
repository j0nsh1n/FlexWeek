// Day agenda and quick Add homework (docs/stage2-contract.md sections 1, 2 and 4).
// The week in memory and its plan give the day's sessions and their times, so edits show at
// once. GET /api/day adds the day's workload and each due-soon homework's unplanned minutes.

const PHONE_QUERY = "(max-width: 800px)";
// The homework the quick dialog edits, or null when it adds new homework.
let homeworkEditingId = null;

/** Phone widths start on the day agenda; wider windows start on the week. */
function prefersDayView() {
  try {
    return typeof matchMedia === "function" && Boolean(matchMedia(PHONE_QUERY).matches);
  } catch {
    return false;
  }
}

function todayIso() {
  return currentDateInfo().iso;
}

/** "Tuesday, Sep 15" for a calendar date. */
function dayTitle(isoDay) {
  const date = parseDate(isoDay);
  return date ? DAY_FULL[(date.getUTCDay() + 6) % 7] + ", " + shortDate(isoDay) : "";
}

/** A signed-in session starts on the default view for this screen, on today when this week is shown. */
function resetPlannerView() {
  plannerView = prefersDayView() ? "day" : "week";
  selectedDay = selectedWeek === currentWeekStart() ? todayIso() : selectedWeek;
  dayData = null;
}

function setPlannerView(next) {
  if (next !== "day" && next !== "week") return;
  plannerView = next;
  if (!selectedDay || mondayOf(selectedDay) !== selectedWeek) {
    selectedDay = selectedWeek === currentWeekStart() ? todayIso() : selectedWeek;
  }
  renderWeekNav();
  renderWeek();
  refreshDayData();
}

/** Show a calendar date on the Day view, opening its week first when it belongs to another week. */
async function openDay(isoDay) {
  if (!account || saving || !parseDate(isoDay)) return false;
  const monday = mondayOf(isoDay);
  if (monday !== selectedWeek && !await selectWeek(monday)) return false;
  selectedDay = isoDay;
  dayData = null;
  renderWeekNav();
  renderWeek();
  refreshDayData();
  return true;
}

/** Fetch the day's workload and unplanned minutes; the agenda redraws when they land. */
async function refreshDayData() {
  if (!account || plannerView !== "day" || !selectedDay) return;
  const token = ++dayRequest;
  const asked = selectedDay;
  try {
    const data = await api("/api/day?date=" + asked);
    if (token !== dayRequest || asked !== selectedDay || plannerView !== "day") return;
    dayData = data;
    renderDayAgenda();
  } catch { /* The agenda still shows the week in memory; the numbers come with the next save. */ }
}

/** Open homework due on the day or the next one, or already overdue, ordered by due then id. */
function dueSoonFor(isoDay) {
  const tomorrow = addDaysIso(isoDay, 1);
  return Array.from(assignments.values()).filter(function (item) {
    return !item.completed && item.due.slice(0, 10) <= tomorrow;
  }).sort(byDue);
}

function isWorkSession(block) {
  return block.kind === "flexible" || (block.kind === "locked" && block.pomodoro_role === "work" && Boolean(block.assignment_id));
}

/**
 * Where a block sits on a day of the week on screen. Its start when it is on that day, null when it
 * is not planned yet, and undefined when the plan put it on another day.
 */
function placementOn(block, dayIndex) {
  const trace = weekState().trace;
  const placed = trace && (trace.placed || []).find(function (item) { return item.id === block.id; });
  if (placed && placed.start) return placed.days.indexOf(dayIndex) !== -1 ? placed.start : undefined;
  if (block.start) return occurrenceDays(block).indexOf(dayIndex) !== -1 ? block.start : undefined;
  return null;
}

function agendaFor(isoDay) {
  const dayIndex = dayOffset(selectedWeek, isoDay);
  const sessions = [];
  const fixed = [];
  weekState().blocks.forEach(function (block) {
    if ((block.days || []).indexOf(dayIndex) === -1 || (block.missed_days || []).indexOf(dayIndex) !== -1) return;
    const start = placementOn(block, dayIndex);
    if (start === undefined) return;
    if (isWorkSession(block)) sessions.push({ block: block, start: start });
    else if (block.kind === "locked") fixed.push({ block: block, start: start });
  });
  const byStart = function (a, b) {
    return (a.start || "99:99").localeCompare(b.start || "99:99") || a.block.id.localeCompare(b.block.id);
  };
  sessions.sort(byStart);
  fixed.sort(byStart);
  const dueSoon = dueSoonFor(isoDay);
  return { dayIndex: dayIndex, dueSoon: dueSoon, sessions: sessions, fixed: fixed, next: nextActionFor(sessions, dueSoon) };
}

/** Next is always one thing: start the earliest placed session, plan due-soon homework, or add homework. */
function nextActionFor(sessions, dueSoon) {
  const start = sessions.find(function (row) {
    return row.start && !row.block.completed && !(assignmentOf(row.block) || {}).completed;
  });
  if (start) return { kind: "start", row: start };
  const fresh = dayData && dayData.date === selectedDay ? dayData.due_soon || [] : [];
  const unplanned = new Map(fresh.map(function (item) { return [item.id, item.unplanned_min]; }));
  const plan = dueSoon.find(function (item) { return unplanned.get(item.id) > 0; });
  return plan ? { kind: "plan", assignment: plan } : { kind: "add" };
}

function minutesText(minutes) {
  return minutes ? formatDuration(minutes) : "0 min";
}

function renderDayAgenda() {
  const root = document.getElementById("day-agenda");
  if (!root) return;
  root.replaceChildren();
  if (plannerView !== "day" || !selectedDay) return;
  const agenda = agendaFor(selectedDay);
  const heading = document.createElement("h2");
  heading.className = "day-title";
  heading.textContent = dayTitle(selectedDay);
  root.appendChild(heading);
  root.appendChild(workloadSummary());
  if (!agenda.dueSoon.length && !agenda.sessions.length && !agenda.fixed.length) {
    const empty = document.createElement("p");
    empty.className = "agenda-empty";
    empty.textContent = "Nothing is due soon and nothing is planned for " + DAY_FULL[agenda.dayIndex] + ".";
    root.appendChild(empty);
    root.appendChild(addHomeworkButton());
    return;
  }
  agendaSection(root, "Due soon", agenda.dueSoon.map(dueSoonRow));
  agendaSection(root, "Homework today", agenda.sessions.map(function (row) { return sessionRow(row, agenda.dayIndex); }));
  agendaSection(root, "Fixed time", agenda.fixed.map(function (row) { return fixedRow(row, agenda.dayIndex); }));
  root.appendChild(nextLine(agenda));
}

/** Scheduled, recorded focus and free time for the day, from the server once it answers. */
function workloadSummary() {
  const box = document.createElement("div");
  box.className = "workload";
  const load = dayData && dayData.date === selectedDay ? dayData.workload : null;
  box.hidden = !load;
  if (!load) return box;
  const line = document.createElement("p");
  line.textContent = "Scheduled " + minutesText(load.scheduled_min) + " · Focus " + minutesText(load.focus_min) +
    " · Free " + minutesText(load.available_min);
  box.appendChild(line);
  const groups = document.createElement("ul");
  groups.className = "workload-categories";
  (load.by_category || []).forEach(function (group) {
    const item = document.createElement("li");
    item.className = "pill";
    item.textContent = (categoryLabel(group.category) || "Other") + " " + minutesText(group.scheduled_min) +
      (group.focus_min ? ", " + minutesText(group.focus_min) + " focus" : "");
    groups.appendChild(item);
  });
  if (groups.children.length) box.appendChild(groups);
  return box;
}

/** A section with its heading, left out entirely when it has no rows. */
function agendaSection(root, title, rows) {
  if (!rows.length) return;
  const section = document.createElement("section");
  section.className = "agenda-section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const list = document.createElement("ul");
  list.className = "agenda-list";
  rows.forEach(function (row) { list.appendChild(row); });
  section.appendChild(heading);
  section.appendChild(list);
  root.appendChild(section);
}

function agendaRow(title, detail, category, actions) {
  const item = document.createElement("li");
  item.className = "agenda-row";
  const color = categoryColor(category);
  if (color) item.style.borderLeftColor = color;
  const name = document.createElement("strong");
  name.textContent = title;
  const small = document.createElement("small");
  small.textContent = detail;
  const buttons = document.createElement("div");
  buttons.className = "agenda-actions";
  actions.filter(Boolean).forEach(function (action) { buttons.appendChild(action); });
  item.appendChild(name);
  item.appendChild(small);
  item.appendChild(buttons);
  return item;
}

function actionButton(label, accessibleLabel, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary";
  button.textContent = label;
  button.ariaLabel = accessibleLabel;
  button.disabled = saving;
  button.addEventListener("click", handler);
  return button;
}

function addHomeworkButton() {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Add homework";
  button.addEventListener("click", function () { openHomeworkDialog(); });
  return button;
}

function dueSoonRow(item) {
  const overdue = item.due < localStamp();
  return agendaRow(item.title, (overdue ? "Overdue, was due " : "Due ") + dueLabel(item.due), item.category, [
    actionButton("Edit", "Edit " + item.title, function () { editHomework(item.id); }),
    actionButton("Finished", "Mark " + item.title + " finished", function () {
      const session = sessionFor(item.id);
      finishHomework(item.id, session && session.id);
    }),
    actionButton("Start focus", "Start focus on " + item.title, function () { startHomeworkFocus(item.id); }),
  ]);
}

function sessionRow(row, dayIndex) {
  const block = row.block;
  const assignment = assignmentOf(block);
  const done = Boolean(block.completed || (assignment && assignment.completed));
  const time = row.start
    ? row.start + "–" + formatMinute(parseStart(row.start) + block.duration_min)
    : "Not planned yet, " + formatDuration(block.duration_min);
  return agendaRow(block.title, done ? time + " · done" : time, block.category, [
    actionButton("Edit", "Edit " + block.title, function () { openBlockEditor(block, dayIndex); }),
    done ? null : actionButton("Finished", "Mark " + block.title + " finished", function () {
      if (assignment) finishHomework(assignment.id, block.id);
      else toggleCompleted(block.id);
    }),
    done ? null : actionButton("Start focus", "Start focus on " + block.title, function () { startFocus(block.id, dayIndex); }),
  ]);
}

function fixedRow(row, dayIndex) {
  const block = row.block;
  const time = row.start + "–" + formatMinute(parseStart(row.start) + block.duration_min);
  return agendaRow(block.title, time, block.category, [
    actionButton("Edit", "Edit " + block.title, function () { openBlockEditor(block, dayIndex, "occurrence"); }),
  ]);
}

function nextLine(agenda) {
  const line = document.createElement("div");
  line.className = "agenda-next";
  const text = document.createElement("span");
  let action;
  if (agenda.next.kind === "start") {
    const block = agenda.next.row.block;
    text.textContent = "Next: " + block.title + " at " + agenda.next.row.start;
    action = actionButton("Start focus", "Start focus on " + block.title, function () { startFocus(block.id, agenda.dayIndex); });
  } else if (agenda.next.kind === "plan") {
    const item = agenda.next.assignment;
    text.textContent = "Next: plan time for " + item.title;
    action = actionButton(planButtonLabel(), planButtonLabel() + " for " + item.title, function () { planHomework(item.id); });
  } else {
    text.textContent = "Next: add homework";
    action = addHomeworkButton();
  }
  line.appendChild(text);
  line.appendChild(action);
  return line;
}

/** The session to act on for homework: one on the day shown first, then any unfinished one this week. */
function sessionFor(assignmentId) {
  const dayIndex = dayOffset(selectedWeek, selectedDay);
  const own = weekState().blocks.filter(function (block) { return block.assignment_id === assignmentId && !block.completed; });
  return own.find(function (block) { return placementOn(block, dayIndex); }) || own[0] || null;
}

function editHomework(assignmentId) {
  const session = sessionFor(assignmentId);
  if (session) return openBlockEditor(session, dayOffset(selectedWeek, selectedDay));
  return openHomeworkDialog(assignmentId);
}

function startHomeworkFocus(assignmentId) {
  const dayIndex = dayOffset(selectedWeek, selectedDay);
  const own = weekState().blocks.filter(function (block) { return block.assignment_id === assignmentId && !block.completed; });
  const today = own.find(function (block) { return resolveFocusPlacement(block.id, dayIndex); });
  const any = today || own.find(function (block) { return resolveFocusPlacement(block.id); });
  if (!any) {
    setStatus("Plan it first, then start focus on the time it gets.");
    return false;
  }
  return startFocus(any.id, today ? dayIndex : undefined);
}

/** Plan homework: add this week's session for its unplanned time when it has none, then plan the week. */
async function planHomework(assignmentId) {
  if (!account || saving) return false;
  const hasSession = weekState().blocks.some(function (block) { return block.assignment_id === assignmentId && !block.completed; });
  if (!hasSession && continuingAssignments().some(function (entry) { return entry.assignment.id === assignmentId; })) {
    if (!planRestHere(assignmentId)) return false;
    while (saving) await new Promise(function (resolve) { setTimeout(resolve, 50); });
  }
  await solveWeek();
  return true;
}

/** Finished: the homework is done and a session on this day keeps its slot. Later sessions stay stored, unplaced. */
function finishHomework(assignmentId, blockId) {
  if (!account || saving) return false;
  const assignment = assignments.get(assignmentId);
  if (!assignment || assignment.completed) return false;
  const block = blockId ? weekState().blocks.find(function (item) { return item.id === blockId; }) : null;
  if (block && !block.completed) {
    block.completed = true;
    if (block.kind === "flexible") {
      const trace = weekState().trace;
      const placed = trace && (trace.placed || []).find(function (item) { return item.id === block.id; });
      if (placed && placed.start && placed.days.length === 1) {
        block.start = placed.start;
        block.completed_day = placed.days[0];
      } else if (!Number.isInteger(block.completed_day)) {
        block.start = null;
      }
    }
  }
  putAssignment({ ...assignment, completed: true, completed_at: localStamp() });
  noticeAfterSave(commitWeek(undefined, "finishing " + assignment.title), "Finished " + assignment.title + ". Undo brings it back.");
  return true;
}

function showHomeworkError(message) {
  const error = document.getElementById("hw-error");
  error.hidden = !message;
  error.textContent = message || "";
}

/** The quick homework form: title, due date and time, and estimated time. With an id it edits that homework. */
function openHomeworkDialog(assignmentId) {
  if (!account || saving) return false;
  const item = assignmentId ? assignments.get(assignmentId) : null;
  homeworkEditingId = item ? item.id : null;
  const base = selectedDay && selectedDay > todayIso() ? selectedDay : todayIso();
  const [dueDate, dueTime] = item ? item.due.split("T") : [addDaysIso(base, 1), "21:00"];
  const estimate = item ? item.estimate_min : 60;
  document.getElementById("homework-heading").textContent = item ? "Edit " + item.title : "Add homework";
  document.getElementById("hw-save").textContent = item ? "Save changes" : "Add homework";
  document.getElementById("hw-custom").hidden = Boolean(item);
  document.getElementById("hw-title").value = item ? item.title : "";
  document.getElementById("hw-due-date").value = dueDate;
  fillOptions(document.getElementById("hw-due-time"), dueTimeChoices(dueTime));
  document.getElementById("hw-due-time").value = dueTime;
  const choices = DURATION_CHOICES.indexOf(estimate) === -1
    ? DURATION_CHOICES.concat([estimate]).sort(function (a, b) { return a - b; })
    : DURATION_CHOICES;
  fillOptions(document.getElementById("hw-estimate"), choices.map(function (minutes) { return [minutes, formatDuration(minutes)]; }));
  document.getElementById("hw-estimate").value = String(estimate);
  showHomeworkError(null);
  const dialog = document.getElementById("homework-dialog");
  if (typeof dialog.showModal === "function") {
    if (!dialog.open) dialog.showModal();
  } else {
    dialog.open = true;
  }
  return true;
}

function closeHomeworkDialog() {
  const dialog = document.getElementById("homework-dialog");
  if (dialog.open && typeof dialog.close === "function") dialog.close();
  dialog.open = false;
  homeworkEditingId = null;
}

/** New homework from the quick form: the Stage 1 assignment and its session this week, through the editor's checks. */
function homeworkDraft(title, dueDate, dueTime, estimate) {
  const draft = presetDraft("assignments", selectedWeek);
  draft.title = title;
  draft.duration_min = estimate;
  draft.dueDate = dueDate || null;
  draft.dueTime = dueTime;
  draft.days = daysThrough(dueDayInWeek(dueDate), firstPlannableDay(selectedWeek));
  return draft;
}

function saveHomework() {
  if (!account || saving) return false;
  const title = document.getElementById("hw-title").value.trim();
  const dueDate = document.getElementById("hw-due-date").value;
  const dueTime = document.getElementById("hw-due-time").value || "23:59";
  const estimate = Number(document.getElementById("hw-estimate").value);
  if (!title) {
    showHomeworkError("Name the homework.");
    return false;
  }
  if (homeworkEditingId) {
    const item = assignments.get(homeworkEditingId);
    if (!item) return false;
    if (!isNaiveStamp(dueDate + "T" + dueTime)) {
      showHomeworkError("Choose the date it is due.");
      return false;
    }
    putAssignment({ ...item, title: title, due: dueDate + "T" + dueTime, estimate_min: estimate });
    // Sessions carry copies of the title; the server rewrites them, so keep the week on screen in step.
    weekState().blocks.forEach(function (block) { if (block.assignment_id === item.id) block.title = title; });
    closeHomeworkDialog();
    noticeAfterSave(commitWeek(undefined, "editing " + item.title), "Saved " + title + ".");
    return true;
  }
  const draft = homeworkDraft(title, dueDate, dueTime, estimate);
  const problem = draftProblem(draft);
  if (problem) {
    showHomeworkError(problem.message);
    return false;
  }
  applyDraft(draft);
  closeHomeworkDialog();
  noticeAfterSave(commitWeek(undefined, "adding " + title),
    "Added " + title + ". Press " + planButtonLabel() + " to find time for it.");
  return true;
}

/** Choose a time myself: the full editor, keeping the title typed so far. */
function chooseTimeMyself() {
  const title = document.getElementById("hw-title").value;
  closeHomeworkDialog();
  const draft = presetDraft("assignments", selectedWeek);
  draft.title = title;
  if (openEditor(draft, null)) flexDaysTouched = false;
}

document.getElementById("homework-form").addEventListener("submit", function (event) {
  event.preventDefault();
  return saveHomework();
});
document.getElementById("hw-cancel").addEventListener("click", function () { closeHomeworkDialog(); });
document.getElementById("hw-custom").addEventListener("click", function () { chooseTimeMyself(); });
document.getElementById("homework-dialog").addEventListener("cancel", function () { homeworkEditingId = null; });
document.getElementById("add-homework").addEventListener("click", function () { openHomeworkDialog(); });
document.getElementById("view-day").addEventListener("click", function () { setPlannerView("day"); });
document.getElementById("view-week").addEventListener("click", function () { setPlannerView("week"); });
