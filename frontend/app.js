const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const START_HOUR = 6;
const END_HOUR = 23;

const weekEl = document.getElementById("week");
const flexibleEl = document.getElementById("flexible");
const demoEl = document.getElementById("demo");

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

  blocks.filter((b) => b.kind === "locked" && b.start).forEach((block) => {
    block.days.forEach((day) => {
      const startMin = parseStart(block.start);
      const topHour = Math.floor(startMin / 60);
      const row = topHour - START_HOUR;
      if (row < 0 || row >= hours.length) return;
      const offsetMin = startMin - topHour * 60;
      const heightPx = (block.duration_min / 60) * 2.4 * 16;
      const el = document.createElement("div");
      el.className = "block";
      el.textContent = block.title;
      el.style.top = `${(offsetMin / 60) * 2.4}rem`;
      el.style.height = `${Math.max(heightPx / 16, 1.1)}rem`;
      cells[day][row].appendChild(el);
    });
  });

  flexibleEl.innerHTML = "";
  blocks.filter((b) => b.kind === "flexible").forEach((block) => {
    const li = document.createElement("li");
    li.textContent = `${block.title} · ${block.duration_min} min`;
    flexibleEl.appendChild(li);
  });
}

async function loadDemo(name) {
  const res = await fetch(`/api/demos/${name}`);
  const data = await res.json();
  buildGrid(data.blocks);
}

demoEl.addEventListener("change", () => loadDemo(demoEl.value));
loadDemo(demoEl.value);
