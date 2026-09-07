const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const START_HOUR = 6;
const END_HOUR = 23;
const PRIORITY_LABEL = { 1: "test", 2: "quiz", 3: "homework", 4: "reading" };

const weekEl = document.getElementById("week");
const flexibleEl = document.getElementById("flexible");
const demoEl = document.getElementById("demo");
const statusEl = document.getElementById("status");
const solveEl = document.getElementById("solve");
const debugEl = document.getElementById("debug");
const debugStatsEl = document.getElementById("debug-stats");
const debugUnplacedEl = document.getElementById("debug-unplaced");
const flexNoteEl = document.getElementById("flex-note");

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
      el.style.top = `${(offsetMin / 60) * hourH}rem`;
      el.style.height = `${Math.max(((endMin - clippedStart) / 60) * hourH, 1.1)}rem`;
      el.title = block.title + (block.course ? " · " + block.course : "");

      const title = document.createElement("div");
      title.className = "title";
      title.textContent = block.title;
      el.appendChild(title);

      const sub = document.createElement("div");
      sub.className = "sub";
      sub.textContent = block.duration_min + " min";
      el.appendChild(sub);

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

async function loadDemo(name) {
  setStatus("Loading…");
  debugEl.hidden = true;
  flexNoteEl.textContent = "Press Solve to place these around school and sports.";
  try {
    const res = await fetch(`/api/demos/${name}`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    currentBlocks = data.blocks || [];
    buildGrid(currentBlocks);
    const locked = currentBlocks.filter((b) => b.kind === "locked").length;
    const flex = currentBlocks.filter((b) => b.kind === "flexible").length;
    setStatus(name + " · " + locked + " locked, " + flex + " flexible");
  } catch (err) {
    console.error(err);
    currentBlocks = [];
    setStatus("Failed to load demos");
  }
}

async function solveWeek() {
  if (!currentBlocks.length) {
    setStatus("Load a demo first");
    return;
  }
  setStatus("Solving…");
  try {
    const res = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ blocks: currentBlocks }),
    });
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

demoEl.addEventListener("change", () => loadDemo(demoEl.value));
solveEl.addEventListener("click", () => solveWeek());
loadDemo(demoEl.value);
