const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const START_HOUR = 6;
const END_HOUR = 23;
const PRIORITY_LABEL = { 1: "test", 2: "quiz", 3: "homework", 4: "reading" };

const weekEl = document.getElementById("week");
const flexibleEl = document.getElementById("flexible");
const demoEl = document.getElementById("demo");
const statusEl = document.getElementById("status");

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

  blocks.filter((b) => b.kind === "locked" && b.start).forEach((block) => {
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
      el.className = "block";
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

  flexibleEl.innerHTML = "";
  const flex = blocks.filter((b) => b.kind === "flexible");
  if (!flex.length) {
    const empty = document.createElement("li");
    empty.textContent = "No flexible tasks in this demo.";
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

async function loadDemo(name) {
  setStatus("Loading…");
  try {
    const res = await fetch(`/api/demos/${name}`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    const blocks = data.blocks || [];
    buildGrid(blocks);
    const locked = blocks.filter((b) => b.kind === "locked").length;
    const flex = blocks.filter((b) => b.kind === "flexible").length;
    setStatus(name + " · " + locked + " locked, " + flex + " flexible");
  } catch (err) {
    console.error(err);
    setStatus("Failed to load demos");
  }
}

demoEl.addEventListener("change", () => loadDemo(demoEl.value));
loadDemo(demoEl.value);
