const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const START_HOUR = 6;
const END_HOUR = 23;
const PRIORITY_LABEL = { 1: "test", 2: "quiz", 3: "homework", 4: "reading" };
const STORAGE_KEY = "flexweek.week.v1";

const weekEl = document.getElementById("week");
const flexibleEl = document.getElementById("flexible");
const demoEl = document.getElementById("demo");
const statusEl = document.getElementById("status");
const solveEl = document.getElementById("solve");
const debugEl = document.getElementById("debug");
const debugStatsEl = document.getElementById("debug-stats");
const debugUnplacedEl = document.getElementById("debug-unplaced");
const flexNoteEl = document.getElementById("flex-note");
const formEl = document.getElementById("block-form");
const formErrorEl = document.getElementById("form-error");
const formHeadingEl = document.getElementById("form-heading");
const formDeleteEl = document.getElementById("form-delete");
const lockedFieldsEl = document.getElementById("f-locked-fields");
const flexFieldsEl = document.getElementById("f-flex-fields");
const startEl = document.getElementById("f-start");
const dueTimeEl = document.getElementById("f-due-time");

let currentBlocks = [];

function hourRange() {
  const hours = [];
  for (let hour = START_HOUR; hour < END_HOUR; hour += 1) hours.push(hour);
  return hours;
}

function pad(n) {
  return String(n).padStart(2, "0");
}

function parseStart(start) {
  const [h, m] = start.split(":").map(Number);
  return h * 60 + m;
}

function hourHeightRem() {
  const raw = getComputedStyle(document.documentElement).getPropertyValue("--hour-h");
  const value = parseFloat(raw);
  return Number.isFinite(value) ? value : 2.75;
}

function setStatus(msg) {
  statusEl.textContent = msg || "";
}

function slotTimes() {
  const times = [];
  for (let min = START_HOUR * 60; min < END_HOUR * 60; min += 15) {
    times.push(pad(Math.floor(min / 60)) + ":" + pad(min % 60));
  }
  return times;
}

function fillTimeSelect(select, includeBlank) {
  select.innerHTML = "";
  if (includeBlank) {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "—";
    select.appendChild(blank);
  }
  slotTimes().forEach((time) => {
    const opt = document.createElement("option");
    opt.value = time;
    opt.textContent = time;
    select.appendChild(opt);
  });
}

function isValidWeek(data) {
  if (!data || typeof data !== "object" || !Array.isArray(data.blocks)) return false;
  return data.blocks.every(function (block) {
    if (!block || typeof block !== "object") return false;
    if (block.kind !== "locked" && block.kind !== "flexible") return false;
    if (typeof block.title !== "string" || !block.title.trim()) return false;
    if (typeof block.duration_min !== "number" || block.duration_min <= 0 || block.duration_min % 15 !== 0) {
      return false;
    }
    if (!Array.isArray(block.days) || !block.days.length) return false;
    if (block.days.some(function (day) { return day < 0 || day > 6; })) return false;
    if (block.kind === "locked") {
      if (typeof block.start !== "string" || !/^\d{2}:\d{2}$/.test(block.start)) return false;
    }
    return true;
  });
}

function readWeek() {
  let raw;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch (err) {
    return null;
  }
  if (!raw) return null;
  try {
    const data = JSON.parse(raw);
    if (!isValidWeek(data)) return null;
    return data.blocks;
  } catch (err) {
    return null;
  }
}

function saveWeek() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ blocks: currentBlocks }));
  } catch (err) {
    setStatus("Could not save this week");
  }
}

function newId() {
  return "b-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 6);
}

function weekSummary() {
  const locked = currentBlocks.filter(function (b) { return b.kind === "locked"; }).length;
  const flex = currentBlocks.filter(function (b) { return b.kind === "flexible"; }).length;
  return locked + " locked, " + flex + " flexible";
}

function renderWeek() {
  buildGrid(currentBlocks);
  setStatus(weekSummary());
}

function buildGrid(blocks) {
  weekEl.innerHTML = "";
  const corner = document.createElement("div");
  corner.className = "corner";
  weekEl.appendChild(corner);
  DAYS.forEach((day) => {
    const head = document.createElement("div");
    head.className = "day-head";
    head.textContent = day;
    weekEl.appendChild(head);
  });

  const hours = hourRange();
  const hourH = hourHeightRem();
  const cells = Array.from({ length: 7 }, () => []);

  hours.forEach((hour) => {
    const label = document.createElement("div");
    label.className = "hour";
    label.textContent = `${pad(hour)}:00`;
    weekEl.appendChild(label);
    for (let day = 0; day < 7; day += 1) {
      const cell = document.createElement("div");
      cell.className = "cell";
      weekEl.appendChild(cell);
      cells[day].push(cell);
    }
  });

  const visibleEnd = END_HOUR * 60;
  const visibleStart = START_HOUR * 60;

  blocks.filter((b) => b.start).forEach((block) => {
    block.days.forEach((day) => {
      const startMin = parseStart(block.start);
      const endMin = Math.min(visibleEnd, startMin + (block.duration_min || 0));
      const clippedStart = Math.max(visibleStart, startMin);
      if (endMin <= clippedStart) return;

      const topHour = Math.floor(clippedStart / 60);
      const row = topHour - START_HOUR;
      if (row < 0 || row >= hours.length) return;

      const offsetMin = clippedStart - topHour * 60;
      const el = document.createElement("div");
      el.className = "block" + (block.kind === "flexible" ? " flex-block" : "");
      el.dataset.id = block.id;
      el.style.top = `${(offsetMin / 60) * hourH}rem`;
      el.style.height = `${Math.max(((endMin - clippedStart) / 60) * hourH, 1.1)}rem`;
      el.title = block.title + (block.course ? " · " + block.course : "") + " (click to edit)";

      const title = document.createElement("div");
      title.className = "title";
      title.textContent = block.title;
      el.appendChild(title);

      const sub = document.createElement("div");
      sub.className = "sub";
      sub.textContent = block.duration_min + " min";
      el.appendChild(sub);

      el.addEventListener("click", function (event) {
        event.stopPropagation();
        const source = currentBlocks.find(function (item) { return item.id === block.id; });
        if (source) openForm(source.kind, source);
      });

      cells[day][row].appendChild(el);
    });
  });

  renderFlexible(blocks.filter((b) => b.kind === "flexible" && !b.start));
}

function renderFlexible(flex) {
  flexibleEl.innerHTML = "";
  if (!flex.length) {
    const empty = document.createElement("li");
    empty.textContent = "None unplaced.";
    flexibleEl.appendChild(empty);
    return;
  }

  flex.forEach((block) => {
    const li = document.createElement("li");
    li.className = "task-card";
    li.dataset.id = block.id;
    const name = document.createElement("strong");
    name.textContent = block.title;
    li.appendChild(name);

    const pills = document.createElement("div");
    pills.className = "pills";

    function pill(text) {
      const span = document.createElement("span");
      span.className = "pill";
      span.textContent = text;
      pills.appendChild(span);
    }

    pill(block.duration_min + " min");
    pill(PRIORITY_LABEL[block.priority] || "P" + block.priority);
    if (block.energy) pill(block.energy);
    if (block.course) pill(block.course);
    if (block.latest) pill("due " + block.latest);

    li.appendChild(pills);
    li.addEventListener("click", function () {
      const source = currentBlocks.find(function (item) { return item.id === block.id; });
      if (source) openForm(source.kind, source);
    });
    flexibleEl.appendChild(li);
  });
}

function renderDebug(trace) {
  debugEl.hidden = false;
  const placedFlex = (trace.placed || []).filter((b) => b.kind === "flexible").length;
  debugStatsEl.textContent =
    "solve_ms " +
    Number(trace.solve_ms).toFixed(1) +
    " · placed " +
    placedFlex +
    " · unplaced " +
    (trace.unplaced || []).length +
    (trace.complete ? " · complete" : " · incomplete");
  debugUnplacedEl.innerHTML = "";
  const reasonById = {};
  (trace.moves || []).forEach((move) => {
    reasonById[move.block_id] = move.reason;
  });
  (trace.unplaced || []).forEach((block) => {
    const li = document.createElement("li");
    li.textContent = block.title + (reasonById[block.id] ? " · " + reasonById[block.id] : "");
    debugUnplacedEl.appendChild(li);
  });
  if (!(trace.unplaced || []).length) {
    const li = document.createElement("li");
    li.textContent = "All flexible tasks placed.";
    debugUnplacedEl.appendChild(li);
  }
}

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

function openForm(kind, block) {
  const editing = Boolean(block);
  formEl.hidden = false;
  showFormError("");
  document.getElementById("f-kind").value = kind;
  document.getElementById("f-id").value = editing ? block.id : "";
  formHeadingEl.textContent = (editing ? "Edit " : "Add ") + (kind === "locked" ? "locked" : "task");
  formDeleteEl.hidden = !editing;
  lockedFieldsEl.hidden = kind !== "locked";
  flexFieldsEl.hidden = kind !== "flexible";

  document.getElementById("f-title").value = editing ? block.title : "";
  document.getElementById("f-course").value = editing && block.course ? block.course : "";
  document.getElementById("f-duration").value = editing ? String(block.duration_min) : "60";
  setSelectedDays(editing ? block.days : []);
  startEl.value = editing && block.start ? block.start : "16:00";
  document.getElementById("f-priority").value = editing && block.priority ? String(block.priority) : "3";
  document.getElementById("f-energy").value = editing && block.energy ? block.energy : "medium";
  const latest = parseLatest(editing ? block.latest : "");
  document.getElementById("f-due-day").value = latest.day;
  dueTimeEl.value = latest.time || "21:00";
  document.getElementById("f-title").focus();
}

function closeForm() {
  formEl.hidden = true;
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
  const kind = document.getElementById("f-kind").value;
  const title = document.getElementById("f-title").value.trim();
  const durationMsg = durationError(document.getElementById("f-duration").value);
  const days = selectedDays();
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

  const id = document.getElementById("f-id").value || newId();
  const existing = currentBlocks.findIndex(function (item) { return item.id === id; });
  const block = {
    id: id,
    title: title,
    kind: kind,
    duration_min: Number(document.getElementById("f-duration").value),
    days: days,
    priority: Number(document.getElementById("f-priority").value) || 3,
    energy: document.getElementById("f-energy").value || "medium",
    course: document.getElementById("f-course").value.trim() || null,
    earliest: null,
    latest: null,
    start: kind === "locked" ? startEl.value : null,
  };
  if (kind === "flexible") {
    const dueDay = document.getElementById("f-due-day").value;
    const dueTime = dueTimeEl.value;
    if (dueDay !== "" && dueTime) {
      block.latest = DAY_FULL[Number(dueDay)] + " " + dueTime;
    }
  }

  if (existing >= 0) currentBlocks[existing] = block;
  else currentBlocks.push(block);

  closeForm();
  debugEl.hidden = true;
  flexNoteEl.textContent = "Press Solve to place these around school and sports.";
  saveWeek();
  renderWeek();
});

document.getElementById("form-cancel").addEventListener("click", closeForm);

formDeleteEl.addEventListener("click", function () {
  const id = document.getElementById("f-id").value;
  currentBlocks = currentBlocks.filter(function (item) { return item.id !== id; });
  closeForm();
  debugEl.hidden = true;
  saveWeek();
  renderWeek();
});

document.getElementById("add-locked").addEventListener("click", function () {
  openForm("locked", null);
});
document.getElementById("add-flexible").addEventListener("click", function () {
  openForm("flexible", null);
});
document.getElementById("new-week").addEventListener("click", function () {
  currentBlocks = [];
  closeForm();
  debugEl.hidden = true;
  flexNoteEl.textContent = "Add locked school or sports, then homework as tasks.";
  saveWeek();
  renderWeek();
  setStatus("Empty week");
});

async function loadDemo(name) {
  setStatus("Loading…");
  debugEl.hidden = true;
  closeForm();
  flexNoteEl.textContent = "Press Solve to place these around school and sports.";
  try {
    const res = await fetch("/api/demos/" + name);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    currentBlocks = data.blocks || [];
    saveWeek();
    renderWeek();
    setStatus((name || "demo") + " · " + weekSummary());
  } catch (err) {
    console.error(err);
    currentBlocks = [];
    setStatus("Failed to load demos");
  }
}

async function solveWeek() {
  setStatus("Solving…");
  try {
    const res = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ blocks: currentBlocks }),
    });
    if (res.status === 422) {
      setStatus("Duration must be a multiple of 15");
      return;
    }
    if (!res.ok) throw new Error("HTTP " + res.status);
    const trace = await res.json();
    buildGrid(trace.placed || []);
    renderFlexible(trace.unplaced || []);
    renderDebug(trace);
    flexNoteEl.textContent = (trace.unplaced || []).length
      ? "Unplaced after Solve — reasons in Debug."
      : "All flexible tasks are on the grid.";
    const placedFlex = (trace.placed || []).filter((b) => b.kind === "flexible").length;
    setStatus(
      "placed " + placedFlex + " · unplaced " + (trace.unplaced || []).length + " · " + Number(trace.solve_ms).toFixed(1) + " ms"
    );
  } catch (err) {
    console.error(err);
    setStatus("Solve failed");
  }
}

function boot() {
  fillTimeSelect(startEl, false);
  fillTimeSelect(dueTimeEl, true);
  const saved = readWeek();
  if (saved) {
    currentBlocks = saved;
    renderWeek();
    setStatus("Saved week · " + weekSummary());
    return;
  }
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    /* ignore */
  }
  loadDemo(demoEl.value || "alex");
}

demoEl.addEventListener("change", function () {
  loadDemo(demoEl.value);
});
solveEl.addEventListener("click", function () {
  solveWeek();
});
boot();
