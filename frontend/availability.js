// Account-wide protected time and preferred study hours for Stage 4.

const AVAILABILITY_LIMIT = 21;
const AVAILABILITY_KINDS = new Set(["downtime", "commute", "meal"]);
let availabilityDraft = { protected: [], study_windows: [], day_cutoff: null };

function availabilityTime(minute) {
  return pad(Math.floor(minute / 60)) + ":" + pad(minute % 60);
}

function availabilityWindowCopy(window) {
  return {
    ...(window.kind ? { kind: window.kind } : {}),
    days: Array.isArray(window.days) ? window.days.slice() : [],
    start: window.start,
    duration_min: window.duration_min,
  };
}

function availabilityOptions(select, choices, selected) {
  select.replaceChildren();
  choices.forEach(function (choice) {
    const option = document.createElement("option");
    option.value = String(choice[0]);
    option.textContent = choice[1];
    select.appendChild(option);
  });
  select.value = String(selected ?? "");
}

function availabilityDurationOptions(select, start, selected) {
  const end = parseStart(start);
  const choices = [];
  for (let minutes = SNAP_MIN; minutes <= DAY_END_MIN - end; minutes += SNAP_MIN) {
    choices.push([minutes, formatDuration(minutes)]);
  }
  const duration = choices.some(function (choice) { return choice[0] === selected; })
    ? selected : choices[Math.min(3, choices.length - 1)][0];
  availabilityOptions(select, choices, duration);
  return duration;
}

function availabilityDayChoices(window) {
  const days = document.createElement("div");
  days.className = "availability-days";
  DAYS.forEach(function (name, day) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = window.days.includes(day);
    input.addEventListener("change", function () {
      window.days = Array.from(days.children).map(function (child, index) {
        return child.children[0].checked ? index : null;
      }).filter(function (value) { return value !== null; });
      renderAvailabilitySummary();
    });
    label.appendChild(input);
    const text = document.createElement("span");
    text.textContent = name;
    label.appendChild(text);
    days.appendChild(label);
  });
  return days;
}

function availabilitySelectLabel(text, select) {
  const label = document.createElement("label");
  const title = document.createElement("span");
  title.textContent = text;
  label.appendChild(title);
  label.appendChild(select);
  return label;
}

function availabilityRow(window, collection, protectedWindow) {
  const row = document.createElement("div");
  row.className = "availability-row";
  const main = document.createElement("div");
  main.className = "availability-row-main";
  if (protectedWindow) {
    const kind = document.createElement("select");
    availabilityOptions(kind, [
      ["downtime", "Downtime"], ["commute", "Commute"], ["meal", "Meal"],
    ], window.kind);
    kind.addEventListener("change", function () { window.kind = kind.value; });
    main.appendChild(availabilitySelectLabel("Type", kind));
  }
  const start = document.createElement("select");
  const starts = [];
  for (let minute = DAY_START_MIN; minute < DAY_END_MIN; minute += SNAP_MIN) {
    starts.push([availabilityTime(minute), availabilityTime(minute)]);
  }
  availabilityOptions(start, starts, window.start);
  const duration = document.createElement("select");
  window.duration_min = availabilityDurationOptions(duration, start.value, window.duration_min);
  start.addEventListener("change", function () {
    window.start = start.value;
    window.duration_min = availabilityDurationOptions(duration, window.start, Number(duration.value));
    renderAvailabilitySummary();
  });
  duration.addEventListener("change", function () {
    window.duration_min = Number(duration.value);
    renderAvailabilitySummary();
  });
  main.appendChild(availabilitySelectLabel("Starts", start));
  main.appendChild(availabilitySelectLabel("Length", duration));
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "secondary availability-remove";
  remove.textContent = "Remove";
  remove.addEventListener("click", function () {
    const index = collection.indexOf(window);
    if (index !== -1) collection.splice(index, 1);
    renderAvailabilityEdit();
  });
  main.appendChild(remove);
  row.appendChild(main);
  row.appendChild(availabilityDayChoices(window));
  return row;
}

function renderAvailabilityEdit() {
  const protectedList = document.getElementById("protected-windows");
  const studyList = document.getElementById("study-windows");
  protectedList.replaceChildren(...availabilityDraft.protected.map(function (window) {
    return availabilityRow(window, availabilityDraft.protected, true);
  }));
  studyList.replaceChildren(...availabilityDraft.study_windows.map(function (window) {
    return availabilityRow(window, availabilityDraft.study_windows, false);
  }));
  document.getElementById("protected-add").disabled = availabilityDraft.protected.length >= AVAILABILITY_LIMIT;
  document.getElementById("study-add").disabled = availabilityDraft.study_windows.length >= AVAILABILITY_LIMIT;
  document.getElementById("availability-cutoff").value = availabilityDraft.day_cutoff || "";
  renderAvailabilitySummary();
}

function beginAvailabilityEdit(preferences) {
  availabilityDraft = {
    protected: (preferences.protected || []).map(availabilityWindowCopy),
    study_windows: (preferences.study_windows || []).map(availabilityWindowCopy),
    day_cutoff: preferences.day_cutoff || null,
  };
  renderAvailabilityEdit();
}

function availabilityWindowProblem(window, protectedWindow) {
  if (protectedWindow && !AVAILABILITY_KINDS.has(window.kind)) return "Choose a protected-time type.";
  if (!Array.isArray(window.days) || !window.days.length || new Set(window.days).size !== window.days.length
      || window.days.some(function (day) { return !Number.isInteger(day) || day < 0 || day > 6; })) {
    return "Choose at least one day for every availability window.";
  }
  if (!/^(?:[01]\d|2[0-3]):(?:00|15|30|45)$/.test(window.start)) return "Choose a 15-minute start time.";
  const start = parseStart(window.start);
  if (start < DAY_START_MIN || start >= DAY_END_MIN || !Number.isInteger(window.duration_min)
      || window.duration_min < SNAP_MIN || window.duration_min % SNAP_MIN
      || start + window.duration_min > DAY_END_MIN) {
    return "Keep every availability window between 06:00 and 23:00 in 15-minute steps.";
  }
  return "";
}

function protectedOverlap(windows) {
  for (let day = 0; day < 7; day += 1) {
    const intervals = windows.filter(function (window) { return window.days.includes(day); }).map(function (window) {
      const start = parseStart(window.start);
      return [start, start + window.duration_min];
    });
    for (let left = 0; left < intervals.length; left += 1) {
      for (let right = left + 1; right < intervals.length; right += 1) {
        if (intervals[left][0] < intervals[right][1] && intervals[right][0] < intervals[left][1]) return true;
      }
    }
  }
  return false;
}

function readAvailabilityEdit() {
  if (availabilityDraft.protected.length > AVAILABILITY_LIMIT
      || availabilityDraft.study_windows.length > AVAILABILITY_LIMIT) {
    return { error: "You can save up to 21 protected and 21 preferred-study windows." };
  }
  for (const window of availabilityDraft.protected) {
    const problem = availabilityWindowProblem(window, true);
    if (problem) return { error: problem };
  }
  for (const window of availabilityDraft.study_windows) {
    const problem = availabilityWindowProblem(window, false);
    if (problem) return { error: problem };
  }
  if (protectedOverlap(availabilityDraft.protected)) {
    return { error: "Protected times overlap on the same day. Adjust or combine them." };
  }
  if (availabilityDraft.day_cutoff) {
    const cutoff = /^(?:[01]\d|2[0-3]):(?:00|15|30|45)$/.test(availabilityDraft.day_cutoff)
      ? parseStart(availabilityDraft.day_cutoff) : 0;
    if (cutoff < DAY_START_MIN + SNAP_MIN || cutoff > DAY_END_MIN) {
      return { error: "Choose a homework cutoff from 06:15 through 23:00." };
    }
  }
  return { value: {
    protected: availabilityDraft.protected.map(availabilityWindowCopy),
    study_windows: availabilityDraft.study_windows.map(availabilityWindowCopy),
    day_cutoff: availabilityDraft.day_cutoff || null,
  } };
}

function hardAvailabilitySlots(settings) {
  const occupied = Array.from({ length: 7 }, function () { return new Set(); });
  (settings.protected || []).forEach(function (window) {
    const start = parseStart(window.start);
    window.days.forEach(function (day) {
      for (let minute = start; minute < start + window.duration_min; minute += SNAP_MIN) occupied[day].add(minute);
    });
  });
  if (settings.day_cutoff) {
    const cutoff = parseStart(settings.day_cutoff);
    for (let day = 0; day < 7; day += 1) {
      for (let minute = cutoff; minute < DAY_END_MIN; minute += SNAP_MIN) occupied[day].add(minute);
    }
  }
  return occupied;
}

function availabilityEffect(settings) {
  const protectedMinutes = hardAvailabilitySlots(settings).reduce(function (total, slots) {
    return total + slots.size * SNAP_MIN;
  }, 0);
  return {
    protected_min: protectedMinutes,
    remaining_min: (DAY_END_MIN - DAY_START_MIN) * 7 - protectedMinutes,
    study_count: (settings.study_windows || []).length,
  };
}

function renderAvailabilitySummary() {
  const summary = document.getElementById("availability-summary");
  const effect = availabilityEffect(availabilityDraft);
  summary.textContent = formatDuration(effect.protected_min) + " protected each week · "
    + formatDuration(effect.remaining_min) + " left in the weekly planning grid · "
    + effect.study_count + (effect.study_count === 1 ? " preferred window" : " preferred windows");
}

function mergedHardIntervals(settings, day) {
  const values = Array.from(hardAvailabilitySlots(settings)[day]).sort(function (a, b) { return a - b; });
  const intervals = [];
  values.forEach(function (minute) {
    const last = intervals[intervals.length - 1];
    if (last && last[1] === minute) last[1] += SNAP_MIN;
    else intervals.push([minute, minute + SNAP_MIN]);
  });
  return intervals;
}

function appendAvailabilityOverlay(lane, start, duration, className, label) {
  const overlay = document.createElement("div");
  overlay.className = "availability-overlay " + className;
  overlay.style.top = ((start - DAY_START_MIN) / 60) * hourHeightRem() + "rem";
  overlay.style.height = (duration / 60) * hourHeightRem() + "rem";
  overlay.title = label;
  overlay.setAttribute("aria-hidden", "true");
  lane.appendChild(overlay);
}

function renderAvailabilityOverlays(lanes) {
  for (let day = 0; day < 7; day += 1) {
    mergedHardIntervals(prefs, day).forEach(function (interval) {
      appendAvailabilityOverlay(lanes[day], interval[0], interval[1] - interval[0], "protected-time", "Protected time");
    });
    (prefs.study_windows || []).filter(function (window) { return window.days.includes(day); }).forEach(function (window) {
      appendAvailabilityOverlay(lanes[day], parseStart(window.start), window.duration_min, "study-time", "Preferred study hours");
    });
  }
}

const cutoff = document.getElementById("availability-cutoff");
const cutoffChoices = [["", "No cutoff"]];
for (let minute = DAY_START_MIN + SNAP_MIN; minute <= DAY_END_MIN; minute += SNAP_MIN) {
  cutoffChoices.push([availabilityTime(minute), availabilityTime(minute)]);
}
availabilityOptions(cutoff, cutoffChoices, "");
cutoff.addEventListener("change", function () {
  availabilityDraft.day_cutoff = cutoff.value || null;
  renderAvailabilitySummary();
});
document.getElementById("protected-add").addEventListener("click", function () {
  if (availabilityDraft.protected.length >= AVAILABILITY_LIMIT) return;
  availabilityDraft.protected.push({ kind: "downtime", days: [0, 1, 2, 3, 4], start: "18:00", duration_min: 60 });
  renderAvailabilityEdit();
});
document.getElementById("study-add").addEventListener("click", function () {
  if (availabilityDraft.study_windows.length >= AVAILABILITY_LIMIT) return;
  availabilityDraft.study_windows.push({ days: [0, 1, 2, 3, 4], start: "16:00", duration_min: 120 });
  renderAvailabilityEdit();
});
