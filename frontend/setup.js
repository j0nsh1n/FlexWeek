// First-week setup after registering: school hours, one sport, the first
// homework, then Solve. Each step builds an editor draft, so setup checks and
// saves blocks exactly the way the Add dialog does.

const SETUP_STEPS = ["school", "sports", "homework", "solve"];
const setupDialogEl = document.getElementById("setup-dialog");
let setupStep = 0;
const setupSkipped = new Set();

function setupDays(prefix) {
  return DAYS.map(function (_name, day) { return day; }).filter(function (day) {
    return field(prefix + "-day-" + day).checked;
  });
}

function setupFixedDraft(category, prefix, title) {
  const days = setupDays(prefix);
  const draft = newDraft(category, days.length ? days[0] : 0,
    parseStart(field(prefix + "-start").value), parseStart(field(prefix + "-end").value));
  draft.days = days;
  draft.title = title;
  return draft;
}

/** The drafts setup would add, one per step that was not skipped. */
function setupDrafts() {
  const drafts = {};
  if (!setupSkipped.has("school")) drafts.school = setupFixedDraft("class", "setup-school", "School");
  if (!setupSkipped.has("sports")) {
    drafts.sports = setupFixedDraft("exercise", "setup-sports", field("setup-sports-title").value);
  }
  if (!setupSkipped.has("homework")) {
    const dueDay = Number(field("setup-homework-due-day").value);
    const duration = Number(field("setup-homework-duration").value);
    const homework = newDraft("assignments", dueDay, DAY_START_MIN, DAY_START_MIN + duration);
    homework.title = field("setup-homework-title").value;
    homework.dueDay = dueDay;
    homework.dueTime = field("setup-homework-due-time").value;
    homework.days = daysThrough(dueDay, firstPlannableDay(selectedWeek));
    drafts.homework = homework;
  }
  return drafts;
}

function setupStepProblem(step, drafts) {
  const draft = drafts[step];
  if (!draft) return null;
  if (step === "homework" && !draft.title.trim()) return "Name the assignment, or choose Skip this step.";
  if (!draft.days.length) {
    return step === "school" ? "Pick your school days, or choose Skip this step."
      : "Pick the days you practice, or choose Skip this step.";
  }
  const problem = draftProblem(draft);
  return problem ? problem.message : null;
}

function setupSummary(drafts) {
  const lines = [];
  ["school", "sports"].forEach(function (step) {
    const draft = drafts[step];
    if (!draft) return;
    const patch = draftPatch(draft);
    lines.push(patch.title + ": " + patch.days.map(function (day) { return DAYS[day]; }).join(", ") + ", " +
      formatMinute(draft.startMin) + "–" + formatMinute(draft.endMin));
  });
  if (drafts.homework) {
    lines.push(draftPatch(drafts.homework).title + ": " + formatDuration(drafts.homework.duration_min) +
      ", due " + DAY_FULL[drafts.homework.dueDay] + " at " + drafts.homework.dueTime);
  }
  return lines;
}

function showSetupError(message) {
  const error = field("setup-error");
  error.hidden = !message;
  error.textContent = message || "";
}

function renderSetupStep() {
  const step = SETUP_STEPS[setupStep];
  SETUP_STEPS.forEach(function (id) { field("setup-" + id).hidden = id !== step; });
  field("setup-progress").textContent = "Step " + (setupStep + 1) + " of " + SETUP_STEPS.length;
  field("setup-back").hidden = setupStep === 0;
  field("setup-skip").hidden = step === "solve";
  const drafts = setupDrafts();
  const lines = setupSummary(drafts);
  field("setup-next").textContent = step !== "solve" ? "Next" : (lines.length ? "Add to my week and Solve" : "Finish");
  if (step === "solve") {
    const list = field("setup-summary");
    list.replaceChildren();
    (lines.length ? lines : ["Nothing to add. You can add school, practice and homework from the sidebar."])
      .forEach(function (line) {
        const item = document.createElement("li");
        item.textContent = line;
        list.appendChild(item);
      });
  }
  showSetupError(null);
}

function fillSetupDefaults() {
  const school = categoryById("class").preset;
  const sports = categoryById("exercise").preset;
  const starts = slotTimes().map(function (time) { return [time, time]; });
  const ends = starts.slice(1).concat([[formatMinute(DAY_END_MIN), formatMinute(DAY_END_MIN)]]);
  ["setup-school", "setup-sports"].forEach(function (prefix) {
    fillOptions(field(prefix + "-start"), starts);
    fillOptions(field(prefix + "-end"), ends);
  });
  field("setup-school-start").value = school.start;
  field("setup-school-end").value = school.end;
  field("setup-sports-start").value = sports.start;
  field("setup-sports-end").value = sports.end;
  DAYS.forEach(function (_name, day) {
    field("setup-school-day-" + day).checked = school.days.indexOf(day) !== -1;
    field("setup-sports-day-" + day).checked = false;
  });
  field("setup-sports-title").value = "";
  field("setup-homework-title").value = "";
  fillOptions(field("setup-homework-duration"), DURATION_CHOICES.map(function (minutes) {
    return [minutes, formatDuration(minutes)];
  }));
  field("setup-homework-duration").value = String(categoryById("assignments").preset.duration_min);
  fillOptions(field("setup-homework-due-day"), DAY_FULL.map(function (name, day) { return [day, name]; }));
  field("setup-homework-due-day").value = String(Math.min(6, firstPlannableDay(selectedWeek) + 1));
  fillOptions(field("setup-homework-due-time"), starts.slice(1).concat([["23:00", "23:00"]]));
  field("setup-homework-due-time").value = "21:00";
}

function openSetup() {
  if (!account || saving) return false;
  setupStep = 0;
  setupSkipped.clear();
  fillSetupDefaults();
  renderSetupStep();
  if (typeof setupDialogEl.showModal === "function") {
    if (!setupDialogEl.open) setupDialogEl.showModal();
  } else {
    setupDialogEl.open = true;
  }
  return true;
}

function closeSetup() {
  if (setupDialogEl.open && typeof setupDialogEl.close === "function") setupDialogEl.close();
  setupDialogEl.open = false;
}

async function finishSetup() {
  const drafts = setupDrafts();
  closeSetup();
  const added = ["school", "sports", "homework"].filter(function (step) { return drafts[step]; })
    .map(function (step) {
      return { id: newId(), kind: drafts[step].kind, missed_days: [], ...draftPatch(drafts[step]) };
    });
  if (!added.length) {
    setStatus("Setup skipped. Pick a type on the right, then drag on the calendar.");
    return false;
  }
  weekState().blocks = weekState().blocks.concat(added);
  if (!await commitWeek()) return false;
  await solveWeek();
  return true;
}

function advanceSetup() {
  const step = SETUP_STEPS[setupStep];
  if (step === "solve") return finishSetup();
  const problem = setupStepProblem(step, setupDrafts());
  if (problem) {
    showSetupError(problem);
    return false;
  }
  setupStep += 1;
  renderSetupStep();
  return true;
}

field("setup-form").addEventListener("submit", function (event) {
  event.preventDefault();
  return advanceSetup();
});
field("setup-skip").addEventListener("click", function () {
  setupSkipped.add(SETUP_STEPS[setupStep]);
  setupStep += 1;
  renderSetupStep();
});
field("setup-back").addEventListener("click", function () {
  setupStep = Math.max(0, setupStep - 1);
  setupSkipped.delete(SETUP_STEPS[setupStep]);
  renderSetupStep();
});
field("setup-close").addEventListener("click", closeSetup);
field("setup-open").addEventListener("click", openSetup);
