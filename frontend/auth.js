function signedOut(message = "Sign in to open your week.", preserve = true) {
  const pending = account ? dirtyWeeks() : [];
  if (preserve && pending.length) {
    suspendedDrafts.set(account.id, pending.map(function (weekStart) {
      const state = weekState(weekStart);
      return { weekStart: weekStart, blocks: structuredClone(state.blocks), revision: state.revision };
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
  hideContextMenu();
  if (gridGesture) clearGhost(gridGesture.lane);
  gridGesture = null;
  weeks.clear();
  savedWeeks = [];
  selectedWeek = currentWeekStart();
  saving = false;
  focusBusy = false;
  weekEl.replaceChildren();
  flexibleEl.replaceChildren();
  debugStatsEl.textContent = "";
  debugUnplacedEl.replaceChildren();
  debugMovesEl.replaceChildren();
  formEl.reset();
  closeForm();
  planner.hidden = true;
  debugEl.hidden = true;
  authPanel.hidden = false;
  document.getElementById("account-controls").hidden = true;
  document.getElementById("account-name").textContent = "";
  document.getElementById("import-panel").hidden = true;
  saveActions.hidden = true;
  document.documentElement.dataset.theme = "nocturne";
  lockEditor(false);
  setStatus(message);
}

async function loadAccount(identity) {
  epoch += 1;
  const loadEpoch = epoch;
  account = identity;
  const asked = currentWeekStart();
  try {
    const [week, saved, preferences] = await Promise.all([
      api("/api/week?week_start=" + asked), api("/api/weeks"), api("/api/preferences"),
    ]);
    if (loadEpoch !== epoch) return;
    weeks.clear();
    savedWeeks = Array.isArray(saved.weeks) ? saved.weeks.slice() : [];
    selectedWeek = isWeekStart(week.week_start) ? week.week_start : asked;
    const state = weekState();
    state.blocks = week.blocks;
    state.revision = week.revision;
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
    renderWeekNav();
    renderWeek();
    setStatus(state.dirty ? "Unsaved edits restored. " + (state.conflict ? "Download your draft and reload the newer week." : "Press Retry save.") : weekStatus());
    try {
      document.getElementById("import-panel").hidden = !localStorage.getItem(STORAGE_KEY);
    } catch { document.getElementById("import-panel").hidden = true; }
  } catch (error) {
    if (loadEpoch === epoch) signedOut("Could not open your week. " + error.message);
  }
}

document.getElementById("auth-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const action = event.submitter?.value || "login";
  const authEpoch = epoch;
  form.querySelectorAll("button").forEach(el => { el.disabled = true; });
  document.getElementById("auth-error").textContent = "";
  try {
    const identity = await api("/api/auth/" + action, { method: "POST", body: JSON.stringify({
      username: document.getElementById("username").value,
      password: document.getElementById("password").value,
    }) }, false);
    document.getElementById("password").value = "";
    channel?.postMessage("session-changed");
    await loadAccount(identity);
  } catch (error) {
    if (authEpoch === epoch) document.getElementById("auth-error").textContent = error.message;
  } finally { form.querySelectorAll("button").forEach(el => { el.disabled = false; }); }
});

document.getElementById("logout").addEventListener("click", async () => {
  if (saving || (dirtyWeeks().length && !confirm("Sign out and discard unsaved changes? Download the draft first if you need it."))) return;
  const logoutEpoch = epoch;
  try {
    await api("/api/auth/logout", { method: "POST" });
    if (account) suspendedDrafts.delete(account.id);
    signedOut("Signed out.", false);
    channel?.postMessage("session-changed");
  } catch (error) { if (logoutEpoch === epoch) setStatus("Sign out failed. " + error.message); }
});

if (channel) channel.onmessage = () => signedOut("The account session changed in another window. Sign in to continue.");

async function reconnect() {
  if (account) return;
  const connectionEpoch = epoch;
  setStatus("Connecting…");
  try { await loadAccount(await api("/api/auth/me", {}, false)); }
  catch (error) {
    if (connectionEpoch === epoch) signedOut(error.status === 401 ? "Sign in to open your week." : "Connection failed. " + error.message);
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

reconnect();
