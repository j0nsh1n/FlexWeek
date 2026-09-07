/**
 * FlexWeek Week 1 UI — fetch demos, paint locked blocks, list flexible tasks.
 * No placement / solver logic here.
 */

(function () {
  "use strict";

  const DAY_START = 6; // 06:00
  const DAY_END = 23; // 23:00
  const HOURS = DAY_END - DAY_START; // 17
  const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  const els = {
    select: document.getElementById("demo-select"),
    status: document.getElementById("status"),
    flexibleList: document.getElementById("flexible-list"),
    dayHeaders: document.getElementById("day-headers"),
    timeGutter: document.getElementById("time-gutter"),
    weekGrid: document.getElementById("week-grid"),
  };

  let demos = null;

  function setStatus(msg) {
    els.status.textContent = msg || "";
  }

  function parseLocal(ts) {
    // YYYY-MM-DDTHH:mm — naive local, no timezone math
    const [date, time] = ts.split("T");
    const [y, m, d] = date.split("-").map(Number);
    const [hh, mm] = time.split(":").map(Number);
    return { y, m, d, hh, mm, minutes: hh * 60 + mm };
  }

  function weekMondayDate(weekStart) {
    // week_start is YYYY-MM-DD (Monday)
    const [y, m, d] = weekStart.split("-").map(Number);
    return { y, m, d };
  }

  function dayIndexFromStart(start, weekStart) {
    const s = parseLocal(start);
    const w = weekMondayDate(weekStart);
    const startUtc = Date.UTC(s.y, s.m - 1, s.d);
    const weekUtc = Date.UTC(w.y, w.m - 1, w.d);
    return Math.round((startUtc - weekUtc) / 86400000);
  }

  function minutesFromDayStart(start) {
    return parseLocal(start).minutes - DAY_START * 60;
  }

  function formatClock(hh) {
    const h12 = ((hh + 11) % 12) + 1;
    const ampm = hh < 12 ? "AM" : "PM";
    return h12 + " " + ampm;
  }

  function buildChrome(weekStart) {
    els.dayHeaders.innerHTML = "";
    const corner = document.createElement("div");
    els.dayHeaders.appendChild(corner);

    const w = weekMondayDate(weekStart);
    for (let i = 0; i < 7; i++) {
      const dt = new Date(Date.UTC(w.y, w.m - 1, w.d + i));
      const label = DAY_NAMES[i] + " " + (dt.getUTCMonth() + 1) + "/" + dt.getUTCDate();
      const head = document.createElement("div");
      head.className = "day-head";
      head.textContent = label;
      els.dayHeaders.appendChild(head);
    }

    els.timeGutter.innerHTML = "";
    for (let h = DAY_START; h < DAY_END; h++) {
      const lab = document.createElement("div");
      lab.className = "time-label";
      lab.textContent = formatClock(h);
      els.timeGutter.appendChild(lab);
    }

    els.weekGrid.innerHTML = "";
    for (let i = 0; i < 7; i++) {
      const col = document.createElement("div");
      col.className = "day-col";
      col.dataset.day = String(i);
      els.weekGrid.appendChild(col);
    }
  }

  function paintLocked(blocks, weekStart) {
    const cols = els.weekGrid.querySelectorAll(".day-col");
    const hourH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--hour-h")) || 48;

    blocks
      .filter(function (b) {
        return b.kind === "locked" && b.start;
      })
      .forEach(function (b) {
        const day = dayIndexFromStart(b.start, weekStart);
        if (day < 0 || day > 6) return;

        const startMin = minutesFromDayStart(b.start);
        const dur = b.duration_min || 0;
        // Clip to visible window 06:00–23:00
        const visibleStart = Math.max(0, startMin);
        const visibleEnd = Math.min(HOURS * 60, startMin + dur);
        if (visibleEnd <= visibleStart) return;

        const top = (visibleStart / 60) * hourH;
        const height = Math.max(18, ((visibleEnd - visibleStart) / 60) * hourH);

        const el = document.createElement("div");
        el.className = "block";
        el.style.top = top + "px";
        el.style.height = height + "px";
        el.title = b.title + (b.course ? " · " + b.course : "");

        const title = document.createElement("div");
        title.className = "title";
        title.textContent = b.title;
        el.appendChild(title);

        if (dur) {
          const sub = document.createElement("div");
          sub.className = "sub";
          sub.textContent = dur + " min";
          el.appendChild(sub);
        }

        cols[day].appendChild(el);
      });
  }

  function renderFlexible(blocks) {
    els.flexibleList.innerHTML = "";
    const flex = blocks.filter(function (b) {
      return b.kind === "flexible";
    });

    if (!flex.length) {
      const empty = document.createElement("li");
      empty.className = "task-card";
      empty.textContent = "No flexible tasks in this demo.";
      els.flexibleList.appendChild(empty);
      return;
    }

    flex.forEach(function (b) {
      const li = document.createElement("li");
      li.className = "task-card";

      const h = document.createElement("h3");
      h.textContent = b.title;
      li.appendChild(h);

      const meta = document.createElement("div");
      meta.className = "task-meta";

      function pill(text) {
        const s = document.createElement("span");
        s.className = "pill";
        s.textContent = text;
        meta.appendChild(s);
      }

      pill(b.duration_min + " min");
      pill("P" + b.priority);
      pill(b.energy);
      if (b.course) pill(b.course);
      if (b.latest) pill("due " + b.latest.replace("T", " "));

      li.appendChild(meta);
      els.flexibleList.appendChild(li);
    });
  }

  function renderDemo(key) {
    if (!demos || !demos[key]) {
      setStatus("Demo not found");
      return;
    }
    const demo = demos[key];
    const weekStart = demo.week_start || "2026-09-07";
    buildChrome(weekStart);
    paintLocked(demo.blocks || [], weekStart);
    renderFlexible(demo.blocks || []);
    setStatus((demo.label || key) + " · " + (demo.blocks || []).length + " blocks");
  }

  async function load() {
    setStatus("Loading demos…");
    try {
      const res = await fetch("/api/demos");
      if (!res.ok) throw new Error("HTTP " + res.status);
      demos = await res.json();
      const initial = els.select.value || "alex";
      renderDemo(initial);
    } catch (err) {
      console.error(err);
      setStatus("Failed to load demos");
    }
  }

  els.select.addEventListener("change", function () {
    renderDemo(els.select.value);
  });

  load();
})();
