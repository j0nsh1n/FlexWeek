// Read-only month navigation. Month snapshots never enter the editable week or assignment stores.

const MONTH_FULL = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const FIRST_MONTH = "2000-01";
const LAST_MONTH = "2099-12";

let selectedMonth = null;
let monthSnapshot = null;
let monthLoading = false;
let monthError = null;
let monthRequest = 0;

function monthTitle(month) {
  const match = /^(\d{4})-(\d{2})$/.exec(String(month || ""));
  if (!match) return "Month";
  return MONTH_FULL[Number(match[2]) - 1] + " " + match[1];
}

function monthForView(view) {
  const anchor = view === "day" && selectedDay ? selectedDay : dateForDay(selectedWeek, 3);
  const month = anchor ? anchor.slice(0, 7) : currentDateInfo().iso.slice(0, 7);
  return month < FIRST_MONTH ? FIRST_MONTH : month > LAST_MONTH ? LAST_MONTH : month;
}

function shiftedMonth(month, amount) {
  const match = /^(\d{4})-(\d{2})$/.exec(String(month || ""));
  if (!match) return null;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1 + amount, 1));
  const next = date.getUTCFullYear() + "-" + pad(date.getUTCMonth() + 1);
  return next >= FIRST_MONTH && next <= LAST_MONTH ? next : null;
}

function clearMonthState() {
  monthRequest += 1;
  selectedMonth = null;
  monthSnapshot = null;
  monthLoading = false;
  monthError = null;
  const calendar = document.getElementById("month-calendar");
  if (calendar) calendar.replaceChildren();
  const state = document.getElementById("month-state");
  if (state) state.replaceChildren();
  ["month-overdue", "month-projects"].forEach(function (id) {
    const list = document.getElementById(id);
    if (list) list.replaceChildren();
  });
  ["month-overdue-section", "month-projects-section", "month-saved-warning"].forEach(function (id) {
    const section = document.getElementById(id);
    if (section) section.hidden = true;
  });
}

function openMonthView() {
  if (!account || saving) return false;
  selectedMonth = monthForView(plannerView);
  plannerView = "month";
  monthSnapshot = null;
  monthError = null;
  renderWeekNav();
  renderWeek();
  refreshMonthData();
  return true;
}

function shiftSelectedMonth(amount) {
  const next = shiftedMonth(selectedMonth, amount);
  if (!next || plannerView !== "month") return false;
  selectedMonth = next;
  renderWeekNav();
  refreshMonthData();
  return true;
}

function openCurrentMonth() {
  if (plannerView !== "month") return false;
  const current = currentDateInfo().iso.slice(0, 7);
  if (current < FIRST_MONTH || current > LAST_MONTH) return false;
  selectedMonth = current;
  renderWeekNav();
  refreshMonthData();
  return true;
}

function currentMonthRequest(token, asked, requestEpoch, accountId) {
  return token === monthRequest && requestEpoch === epoch && account && account.id === accountId &&
    plannerView === "month" && selectedMonth === asked;
}

async function refreshMonthData() {
  if (!account || plannerView !== "month" || !selectedMonth) return false;
  const token = ++monthRequest;
  const asked = selectedMonth;
  const requestEpoch = epoch;
  const accountId = account.id;
  monthSnapshot = null;
  monthLoading = true;
  monthError = null;
  renderMonthView();
  try {
    const data = await api("/api/month?month=" + asked);
    if (!currentMonthRequest(token, asked, requestEpoch, accountId)) return false;
    if (!data || data.month !== asked || !Array.isArray(data.days) ||
        !Array.isArray(data.deadlines) || !Array.isArray(data.projects) || !Array.isArray(data.overdue)) {
      throw new Error("The server returned an invalid month.");
    }
    monthSnapshot = data;
    monthLoading = false;
    renderMonthView();
    return true;
  } catch (error) {
    if (!currentMonthRequest(token, asked, requestEpoch, accountId)) return false;
    monthLoading = false;
    monthError = error.message || "Could not load this month.";
    renderMonthView();
    return false;
  }
}

function fullDateLabel(isoDay) {
  const date = parseDate(isoDay);
  if (!date) return isoDay;
  return DAY_FULL[(date.getUTCDay() + 6) % 7] + ", " + MONTH_FULL[date.getUTCMonth()] +
    " " + date.getUTCDate() + ", " + date.getUTCFullYear();
}

function monthDaySummary(day) {
  const parts = [];
  if (day.session_count) parts.push(day.session_count + " study");
  if (day.locked_count) parts.push(day.locked_count + " fixed");
  if (day.scheduled_min) parts.push(formatDuration(day.scheduled_min));
  return parts.join(" · ");
}

async function openMonthDay(isoDay) {
  if (plannerView !== "month" || !selectedMonth) return false;
  const opened = await openDay(isoDay);
  if (!opened || !account || plannerView !== "month") return false;
  plannerView = "day";
  selectedDay = isoDay;
  renderWeekNav();
  renderWeek();
  refreshDayData();
  return true;
}

function monthDateButton(day, deadlines) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "month-day" + (day.in_month ? "" : " is-outside");
  button.dataset.date = day.date;
  const today = day.date === currentDateInfo().iso;
  if (today) button.classList.add("is-today");
  const date = parseDate(day.date);
  const dateLabel = document.createElement("span");
  dateLabel.className = "month-day-date";
  const weekday = document.createElement("span");
  weekday.className = "month-day-weekday-mobile";
  weekday.textContent = DAY_FULL[(date.getUTCDay() + 6) % 7].slice(0, 3);
  const number = document.createElement("span");
  number.className = "month-day-number";
  number.textContent = String(date.getUTCDate());
  dateLabel.appendChild(weekday);
  dateLabel.appendChild(number);
  button.appendChild(dateLabel);
  if (today) {
    const marker = document.createElement("span");
    marker.className = "month-today-marker";
    marker.textContent = "Today";
    button.appendChild(marker);
  }
  deadlines.forEach(function (item) {
    const due = document.createElement("span");
    due.className = "month-due" + (item.completed ? " is-completed" : "");
    due.textContent = item.title + (item.completed ? " · Done" : "");
    button.appendChild(due);
  });
  const summaryText = monthDaySummary(day);
  if (summaryText) {
    const summary = document.createElement("span");
    summary.className = "month-day-summary";
    summary.textContent = summaryText;
    button.appendChild(summary);
  }
  const outside = day.in_month ? "" : ", outside " + monthTitle(selectedMonth);
  const dueText = deadlines.length ? ", " + deadlines.map(function (item) {
    return item.title + (item.completed ? " completed" : " due");
  }).join(", ") : "";
  button.ariaLabel = fullDateLabel(day.date) + outside + dueText + (summaryText ? ", " + summaryText : "");
  button.addEventListener("click", function () { openMonthDay(day.date); });
  return button;
}

function renderMonthCalendar(snapshot) {
  const root = document.getElementById("month-calendar");
  root.replaceChildren();
  const grid = document.createElement("div");
  grid.className = "month-grid";
  DAYS.forEach(function (name) {
    const heading = document.createElement("div");
    heading.className = "month-weekday";
    heading.textContent = name;
    heading.ariaHidden = "true";
    grid.appendChild(heading);
  });
  const byId = new Map(snapshot.deadlines.map(function (item) { return [item.id, item]; }));
  snapshot.days.forEach(function (day, index) {
    const cell = document.createElement("div");
    cell.className = "month-cell";
    if (index === 0) {
      const date = parseDate(day.date);
      cell.style.gridColumnStart = String(((date.getUTCDay() + 6) % 7) + 1);
    }
    const due = (day.due_ids || []).map(function (id) { return byId.get(id); }).filter(Boolean);
    cell.appendChild(monthDateButton(day, due));
    grid.appendChild(cell);
  });
  root.appendChild(grid);
}

function deadlineRow(item) {
  const row = document.createElement("li");
  const title = document.createElement("strong");
  title.textContent = item.title;
  const detail = document.createElement("span");
  detail.textContent = "Due " + dueLabel(item.due) + (item.unplanned_min ? " · " + formatDuration(item.unplanned_min) + " left" : "");
  row.appendChild(title);
  row.appendChild(detail);
  return row;
}

function projectRow(item) {
  const row = deadlineRow(item);
  row.className = "month-project";
  if ((item.session_dates || []).length) {
    const dates = document.createElement("div");
    dates.className = "month-project-dates";
    const label = document.createElement("span");
    label.textContent = "Study dates";
    dates.appendChild(label);
    item.session_dates.forEach(function (date) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary";
      button.textContent = shortDate(date);
      button.ariaLabel = "Open " + fullDateLabel(date) + " in Day view";
      button.addEventListener("click", function () { openMonthDay(date); });
      dates.appendChild(button);
    });
    row.appendChild(dates);
  }
  const indicators = [];
  if (item.checklist_total) indicators.push("Checklist " + item.checklist_done + "/" + item.checklist_total);
  if (item.has_notes) indicators.push("Notes");
  if (item.has_links) indicators.push("Links");
  if (indicators.length) {
    const detail = document.createElement("span");
    detail.className = "month-project-indicators";
    detail.textContent = indicators.join(" · ");
    row.appendChild(detail);
  }
  return row;
}

function renderMonthLists(snapshot) {
  const overdue = document.getElementById("month-overdue");
  overdue.replaceChildren();
  snapshot.overdue.forEach(function (item) { overdue.appendChild(deadlineRow(item)); });
  document.getElementById("month-overdue-section").hidden = !snapshot.overdue.length;
  const projects = document.getElementById("month-projects");
  projects.replaceChildren();
  snapshot.projects.forEach(function (item) { projects.appendChild(projectRow(item)); });
  document.getElementById("month-projects-section").hidden = !snapshot.projects.length;
}

function renderMonthView() {
  if (plannerView !== "month") return;
  const state = document.getElementById("month-state");
  const calendar = document.getElementById("month-calendar");
  const warning = document.getElementById("month-saved-warning");
  warning.hidden = !dirtyWeeks().length && !dirtyAssignments.size;
  document.getElementById("week-prev").disabled = selectedMonth === FIRST_MONTH;
  document.getElementById("week-next").disabled = selectedMonth === LAST_MONTH;
  calendar.replaceChildren();
  document.getElementById("month-overdue").replaceChildren();
  document.getElementById("month-projects").replaceChildren();
  document.getElementById("month-overdue-section").hidden = true;
  document.getElementById("month-projects-section").hidden = true;
  state.replaceChildren();
  state.setAttribute("role", monthError ? "alert" : "status");
  if (monthLoading) {
    state.textContent = "Loading " + monthTitle(selectedMonth) + "…";
    return;
  }
  if (monthError) {
    const message = document.createElement("span");
    message.textContent = "Could not load this month. " + monthError;
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "secondary";
    retry.textContent = "Retry";
    retry.addEventListener("click", refreshMonthData);
    state.appendChild(message);
    state.appendChild(retry);
    return;
  }
  if (!monthSnapshot) return;
  const hasCalendarContent = monthSnapshot.deadlines.length || monthSnapshot.days.some(function (day) {
    return day.in_month && (day.session_count || day.locked_count);
  });
  if (!hasCalendarContent && !monthSnapshot.projects.length && !monthSnapshot.overdue.length) {
    state.textContent = "Nothing is due or scheduled this month.";
  }
  renderMonthCalendar(monthSnapshot);
  renderMonthLists(monthSnapshot);
}

document.getElementById("view-month").addEventListener("click", function () { setPlannerView("month"); });
