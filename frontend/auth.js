const AUTH_SCREENS = {
  register: { screen: "register-screen", form: "register-form", error: "register-error" },
  login: { screen: "login-screen", form: "login-form", error: "login-error" },
};

/** Show one auth screen. Page load opens register; returning after a session opens login. */
function showAuthScreen(name) {
  Object.keys(AUTH_SCREENS).forEach(function (key) {
    const ids = AUTH_SCREENS[key];
    document.getElementById(ids.screen).hidden = key !== name;
    document.getElementById(ids.error).textContent = "";
  });
}

function signedOut(message = "Log in to open your week.", preserve = true, screen = "login") {
  const pending = account ? dirtyWeeks() : [];
  if (preserve && pending.length) {
    suspendedDrafts.set(account.id, pending.map(function (weekStart) {
      const state = weekState(weekStart);
      return { weekStart: weekStart, blocks: structuredClone(state.blocks), revision: state.revision };
    }));
    // A restored week may point at assignments that were never saved.
    suspendedAssignments.set(account.id, Array.from(dirtyAssignments).map(function (id) {
      return structuredClone(assignments.get(id));
    }));
  }
  epoch += 1;
  account = null;
  syncReminderLoop();
  stopPhase7Loops();
  resetFocusTimer(false);
  firedReminders.clear();
  firedAlarms.clear();
  snoozedAlarms.clear();
  pendingAlarms = [];
  alarmQueue = [];
  activeAlarm = null;
  stopTone();
  activeNotifications.forEach(function (notification) {
    try { notification.close(); } catch (err) { /* ignore */ }
  });
  activeNotifications.clear();
  clearTimeout(showReminderToast._timer);
  const toast = document.getElementById("reminder-toast");
  if (toast) { toast.hidden = true; toast.textContent = ""; }
  const preferencesDialog = document.getElementById("prefs-dialog");
  if (preferencesDialog && typeof preferencesDialog.close === "function") preferencesDialog.close();
  const alarmDialog = document.getElementById("alarm-dialog");
  if (alarmDialog && typeof alarmDialog.close === "function") alarmDialog.close();
  if (typeof clearStage3State === "function") clearStage3State();
  if (typeof clearAdaptState === "function") clearAdaptState();
  hideContextMenu();
  if (gridGesture) clearGhost(gridGesture.lane);
  gridGesture = null;
  weeks.clear();
  assignments.clear();
  dirtyAssignments.clear();
  plannedLater.clear();
  clearHistory();
  savedWeeks = [];
  selectedWeek = currentWeekStart();
  saving = false;
  focusBusy = false;
  weekEl.replaceChildren();
  flexibleEl.replaceChildren();
  document.getElementById("continuing").replaceChildren();
  document.getElementById("continuing-section").hidden = true;
  debugStatsEl.textContent = "";
  debugUnplacedEl.replaceChildren();
  debugMovesEl.replaceChildren();
  formEl.reset();
  closeForm();
  closeSetup();
  planner.hidden = true;
  debugEl.hidden = true;
  authPanel.hidden = false;
  showAuthScreen(screen);
  document.getElementById("reconnect").hidden = true;
  document.getElementById("account-controls").hidden = true;
  document.getElementById("account-name").textContent = "";
  document.getElementById("import-panel").hidden = true;
  saveActions.hidden = true;
  // Signed-out screens follow the device; an account's saved choice applies after login.
  applyTheme("system");
  lockEditor(false);
  setStatus(message);
}

async function loadAccount(identity) {
  epoch += 1;
  const loadEpoch = epoch;
  account = identity;
  const asked = currentWeekStart();
  try {
    const [week, saved, preferences, owned] = await Promise.all([
      api("/api/week?week_start=" + asked), api("/api/weeks"), api("/api/preferences"),
      api("/api/assignments?week_start=" + asked + "&include_completed=true"),
    ]);
    if (loadEpoch !== epoch) return;
    weeks.clear();
    assignments.clear();
    dirtyAssignments.clear();
    plannedLater.clear();
    const ownedItems = owned && Array.isArray(owned.assignments) ? owned.assignments : [];
    ownedItems.forEach(function (item) { assignments.set(item.id, item); });
    savedWeeks = Array.isArray(saved.weeks) ? saved.weeks.slice() : [];
    selectedWeek = isWeekStart(week.week_start) ? week.week_start : asked;
    const state = weekState();
    state.blocks = week.blocks;
    state.revision = week.revision;
    rememberPlannedLater(selectedWeek, ownedItems, week.blocks);
    // History belongs to one account and one page load.
    clearHistory();
    noteLoaded("week", selectedWeek, week.blocks, week.revision, null);
    ownedItems.forEach(function (item) { noteLoaded("assignment", item.id, assignmentBody(item), item.revision, null); });
    (suspendedAssignments.get(account.id) || []).forEach(putAssignment);
    suspendedAssignments.delete(account.id);
    const suspendedDraft = suspendedDrafts.get(account.id);
    if (suspendedDraft) {
      suspendedDraft.forEach(function (draft) {
        const target = weekState(draft.weekStart);
        target.blocks = draft.blocks;
        // Only the week just fetched has a known server revision to compare.
        target.conflict = draft.weekStart === selectedWeek && draft.revision !== target.revision;
        target.revision = draft.revision;
        target.dirty = true;
      });
      suspendedDrafts.delete(account.id);
    }
    applyPreferences(preferences);
    authPanel.hidden = true;
    planner.hidden = false;
    document.getElementById("account-controls").hidden = false;
    document.getElementById("account-name").textContent = identity.username;
    saveActions.hidden = !state.dirty;
    document.getElementById("retry-save").disabled = state.conflict;
    lockEditor(false);
    resetPlannerView();
    renderWeekNav();
    renderWeek();
    setStatus(state.dirty ? "Unsaved edits restored. " + (state.conflict ? "Download your draft and reload the newer week." : "Press Retry save.") : weekStatus());
    restoreFocus();
    refreshDayData();
    if (typeof prepareStage3Account === "function") prepareStage3Account();
    if (typeof prepareAdaptAccount === "function") prepareAdaptAccount();
    try {
      document.getElementById("import-panel").hidden = !localStorage.getItem(STORAGE_KEY);
    } catch { document.getElementById("import-panel").hidden = true; }
  } catch (error) {
    if (loadEpoch === epoch) signedOut("Could not open your week. " + error.message);
  }
}

async function submitAuth(action) {
  const ids = AUTH_SCREENS[action];
  const username = document.getElementById(action + "-username");
  const password = document.getElementById(action + "-password");
  const form = document.getElementById(ids.form);
  const authEpoch = epoch;
  form.querySelectorAll("button").forEach(el => { el.disabled = true; });
  document.getElementById(ids.error).textContent = "";
  try {
    const identity = await api("/api/auth/" + action, { method: "POST", body: JSON.stringify({
      username: username.value, password: password.value,
    }) }, false);
    password.value = "";
    channel?.postMessage("session-changed");
    await loadAccount(identity);
    // A new account starts empty, so walk it through its first week instead of a blank grid.
    if (action === "register" && account && !weekState().blocks.length) openSetup();
  } catch (error) {
    if (authEpoch === epoch) document.getElementById(ids.error).textContent = error.message;
  } finally { form.querySelectorAll("button").forEach(el => { el.disabled = false; }); }
}

Object.keys(AUTH_SCREENS).forEach(function (action) {
  document.getElementById(AUTH_SCREENS[action].form).addEventListener("submit", function (event) {
    event.preventDefault();
    return submitAuth(action);
  });
});

function switchAuthScreen(from, to) {
  const typed = document.getElementById(from + "-username").value;
  const target = document.getElementById(to + "-username");
  if (typed && !target.value) target.value = typed;
  showAuthScreen(to);
  if (typeof target.focus === "function") target.focus();
}
document.getElementById("show-login").addEventListener("click", () => switchAuthScreen("register", "login"));
document.getElementById("show-register").addEventListener("click", () => switchAuthScreen("login", "register"));

document.getElementById("logout").addEventListener("click", async () => {
  if (saving || (dirtyWeeks().length && !confirm("Log out and discard unsaved changes? Download the draft first if you need it."))) return;
  const logoutEpoch = epoch;
  try {
    await api("/api/auth/logout", { method: "POST" });
    if (account) {
      suspendedDrafts.delete(account.id);
      suspendedAssignments.delete(account.id);
      forgetFocus(account.id);
    }
    signedOut("Logged out.", false);
    channel?.postMessage("session-changed");
  } catch (error) { if (logoutEpoch === epoch) setStatus("Log out failed. " + error.message); }
});

if (channel) channel.onmessage = () => signedOut("The account changed in another window. Log in to continue.");

async function reconnect() {
  if (account) return;
  const connectionEpoch = epoch;
  setStatus("Connecting…");
  try { await loadAccount(await api("/api/auth/me", {}, false)); }
  catch (error) {
    if (connectionEpoch !== epoch) return;
    const offline = error.status !== 401;
    signedOut(offline ? "Could not reach FlexWeek. " + error.message : "Create an account to start planning.", true, "register");
    document.getElementById("reconnect").hidden = !offline;
  }
}
document.getElementById("reconnect").addEventListener("click", reconnect);
window.addEventListener("beforeunload", event => {
  if (dirtyWeeks().length) { event.preventDefault(); event.returnValue = ""; }
});
window.addEventListener("pageshow", event => { if (event.persisted) { signedOut(); reconnect(); } });
document.addEventListener("visibilitychange", async () => {
  if (document.hidden || !account) return;
  try { await api("/api/auth/me"); } catch { /* Session expiry is handled by api. */ }
});

/** After the desktop app reopened a page that stopped, put the week and its Solve result back. */
async function finishRecovery() {
  // A later reload is an ordinary one.
  if (typeof history !== "undefined") history.replaceState(null, "", location.pathname);
  await reconnect();
  if (!account) return;
  if (weekState().blocks.some(function (block) { return block.kind === "flexible"; })) await solveWeek();
  setStatus("FlexWeek reopened after a display problem. " + statusEl.textContent);
}

if (pageRecovered) finishRecovery();
else reconnect();
