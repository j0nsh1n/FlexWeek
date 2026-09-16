// Account recovery, identity and explicit account transfer shared by both clients.

let stage6ReferenceEpoch = null;
let stage6RecoveryCodes = [];
let stage6RegistrationCodes = false;
let stage6Import = null;
let stage6Busy = false;
let stage6TransferLimit = 256 * 1024;

function accessElement(id) {
  return document.getElementById(id);
}

function accessError(id, message) {
  const target = accessElement(id);
  target.textContent = message || "";
  target.hidden = !message;
}

function openAccessDialog(dialog) {
  const settings = accessElement("prefs-dialog");
  if (settings && settings.open && typeof settings.close === "function") settings.close();
  if (typeof dialog.showModal === "function") {
    if (!dialog.open) dialog.showModal();
  } else {
    dialog.open = true;
  }
}

function closeAccessDialog(dialog) {
  if (typeof dialog.close === "function") dialog.close();
  else dialog.open = false;
}

function setAccessFormBusy(form, busy) {
  form.querySelectorAll("button, input").forEach(function (control) { control.disabled = busy; });
}

function renderStage6Storage(info) {
  if (!info || typeof info.label !== "string") return;
  accessElement("account-location-label").textContent = info.label;
  accessElement("prefs-account").textContent = "Signed in as " + info.username;
  accessElement("account-location-origin").textContent = info.origin;
  accessElement("account-sync-note").textContent = info.mode === "hosted"
    ? "This hosted account opens the same saved data in the browser and desktop app. Offline changes do not sync automatically."
    : "This account stays in this device’s local database. It does not sync automatically.";
  if (Number.isInteger(info.transfer_limit_bytes) && info.transfer_limit_bytes > 0) {
    stage6TransferLimit = info.transfer_limit_bytes;
  }
}

function renderRecoveryStatus(remaining) {
  const count = Number.isInteger(remaining) ? remaining : 0;
  accessElement("recovery-status").textContent = count === 0
    ? "No unused recovery codes remain. Replace them before logging out."
    : count === 1
    ? "1 unused recovery code remains."
    : count + " unused recovery codes remain.";
}

async function prepareStage6Account() {
  if (!account || stage6ReferenceEpoch === epoch) return;
  stage6ReferenceEpoch = epoch;
  const loadEpoch = epoch;
  const accountId = account.id;
  const results = await Promise.allSettled([api("/api/storage-info"), api("/api/auth/recovery-status")]);
  if (loadEpoch !== epoch || !account || account.id !== accountId) return;
  if (results[0].status === "fulfilled") renderStage6Storage(results[0].value);
  else {
    accessElement("account-location-label").textContent = "Account location unavailable";
    accessElement("prefs-account").textContent = "Signed in as " + account.username;
    accessElement("account-location-origin").textContent = "";
  }
  if (results[1].status === "fulfilled") renderRecoveryStatus(results[1].value.remaining);
  else accessElement("recovery-status").textContent = "Recovery-code status unavailable.";
  if (results.some(function (result) { return result.status === "rejected"; })) stage6ReferenceEpoch = null;
}

function recoveryCodesText() {
  return ["FlexWeek recovery codes for " + (account ? account.username : "your account"), "",
    ...stage6RecoveryCodes, "", "Each code works once. Keep this file private."].join("\n");
}

function renderRecoveryCodes() {
  const list = accessElement("recovery-codes-list");
  list.replaceChildren();
  stage6RecoveryCodes.forEach(function (code) {
    const item = document.createElement("li");
    const value = document.createElement("code");
    value.textContent = code;
    item.appendChild(value);
    list.appendChild(item);
  });
}

function showRecoveryCodes(codes, afterRegistration = false) {
  if (!account || !Array.isArray(codes) || codes.length !== 8) {
    setStatus("Recovery codes were not returned. Open Settings and replace them before logging out.");
    return false;
  }
  stage6RecoveryCodes = codes.slice();
  stage6RegistrationCodes = afterRegistration;
  accessElement("recovery-codes-intro").textContent = afterRegistration
    ? "Your account is ready. Each code works once if you forget your password. FlexWeek cannot show these codes again."
    : "Your old unused codes no longer work. Save these replacements now; FlexWeek cannot show them again.";
  accessElement("recovery-codes-ack").checked = false;
  accessElement("recovery-codes-done").disabled = true;
  accessError("recovery-codes-error", "");
  renderRecoveryCodes();
  openAccessDialog(accessElement("recovery-codes-dialog"));
  return true;
}

async function copyRecoveryCodes() {
  try {
    if (typeof navigator !== "object" || !navigator.clipboard || !navigator.clipboard.writeText) {
      throw new Error("Clipboard access is unavailable. Download the codes instead.");
    }
    await navigator.clipboard.writeText(recoveryCodesText());
    accessError("recovery-codes-error", "");
    setStatus("Recovery codes copied. Keep them somewhere private.");
  } catch (error) {
    accessError("recovery-codes-error", error.message);
  }
}

function downloadRecoveryCodes() {
  if (!stage6RecoveryCodes.length) return;
  downloadText("flexweek-recovery-codes-" + account.username + ".txt", recoveryCodesText(), "text/plain");
  setStatus("Recovery codes downloaded. Keep that file private.");
}

function finishRecoveryCodes() {
  if (!accessElement("recovery-codes-ack").checked) return;
  const startSetup = stage6RegistrationCodes && account && !weekState().blocks.length;
  closeAccessDialog(accessElement("recovery-codes-dialog"));
  stage6RecoveryCodes = [];
  stage6RegistrationCodes = false;
  renderRecoveryCodes();
  if (startSetup) openSetup();
}

function accountHasUnsavedChanges() {
  return dirtyWeeks().length > 0 || dirtyAssignments.size > 0;
}

function openTransferDialog() {
  if (!account || saving) return;
  if (accountHasUnsavedChanges()) {
    setStatus("Save, retry or download your unsaved changes before transferring account data.");
    return;
  }
  resetTransferPreview();
  accessError("transfer-error", "");
  openAccessDialog(accessElement("transfer-dialog"));
}

function transferOperationId() {
  if (typeof crypto === "object" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return "transfer-" + Date.now().toString(16) + "-" + Math.random().toString(16).slice(2);
}

function transferSnapshotProblem(snapshot) {
  if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)) return "This is not a FlexWeek account file.";
  if (snapshot.format !== 3) return "Choose a FlexWeek account transfer file. A week export belongs under Import week.";
  const fields = new Set(["format", "exported_at", "username", "weeks", "assignments", "preferences", "routines"]);
  if (Object.keys(snapshot).some(function (key) { return !fields.has(key); })) return "The account file has an unknown field.";
  if (!isNaiveStamp(snapshot.exported_at)) return "The account file has an invalid export time.";
  if (typeof snapshot.username !== "string" || !/^[A-Za-z0-9_]{3,32}$/.test(snapshot.username)) {
    return "The account file has an invalid source username.";
  }
  if (!Array.isArray(snapshot.weeks)) return "The account file has too many or missing weeks.";
  if (!Array.isArray(snapshot.assignments) || snapshot.assignments.length > 1000) {
    return "The account file has too many or missing homework items.";
  }
  if (!Array.isArray(snapshot.routines) || snapshot.routines.length > 50) return "The account file has too many or missing routines.";
  if (!snapshot.preferences || typeof snapshot.preferences !== "object" || Array.isArray(snapshot.preferences)) {
    return "The account file is missing its settings.";
  }
  const assignmentIds = new Set();
  for (let index = 0; index < snapshot.assignments.length; index += 1) {
    const item = snapshot.assignments[index];
    if (!item || typeof item !== "object" || item.id !== (item.body && item.body.id)
        || !Number.isSafeInteger(item.revision) || item.revision < 0) {
      return "Homework " + (index + 1) + " has invalid identity or revision data.";
    }
    const problem = importAssignmentError(item.body, index);
    if (problem) return problem;
    if (assignmentIds.has(item.id)) return "The account file repeats homework " + item.id + ".";
    assignmentIds.add(item.id);
  }
  const weekStarts = new Set();
  for (let index = 0; index < snapshot.weeks.length; index += 1) {
    const week = snapshot.weeks[index];
    if (!week || !isWeekStart(week.week_start) || !Number.isSafeInteger(week.revision) || week.revision < 0) {
      return "Week " + (index + 1) + " has an invalid Monday or revision.";
    }
    if (weekStarts.has(week.week_start)) return "The account file repeats week " + week.week_start + ".";
    weekStarts.add(week.week_start);
    const blockProblem = importBlocksError(week.blocks || []);
    if (blockProblem) return "Week " + week.week_start + ": " + blockProblem;
    for (const block of week.blocks || []) {
      if (block.assignment_id && !assignmentIds.has(block.assignment_id)) {
        return "Week " + week.week_start + " points at homework the account file does not include.";
      }
    }
  }
  const routineIds = new Set();
  for (let index = 0; index < snapshot.routines.length; index += 1) {
    const routine = snapshot.routines[index];
    if (!routine || typeof routine.id !== "string" || !routine.id || routineIds.has(routine.id)
        || typeof routine.name !== "string" || !routine.name.trim() || textLength(routine.name) > 80
        || !Number.isSafeInteger(routine.revision) || routine.revision < 0
        || !isNaiveStamp(routine.created_at) || !isNaiveStamp(routine.updated_at)) {
      return "Routine " + (index + 1) + " has invalid identity, name or history.";
    }
    routineIds.add(routine.id);
    const routineProblem = importBlocksError(routine.blocks || []);
    if (routineProblem || (routine.blocks || []).some(function (block) { return block.kind !== "locked"; })) {
      return "Routine " + (index + 1) + " must contain valid fixed times only.";
    }
  }
  return null;
}

function parseTransferSnapshot(text) {
  if (!text || !text.trim()) return { error: "The account file is empty." };
  let snapshot;
  try { snapshot = JSON.parse(text); }
  catch { return { error: "The account file is not valid JSON." }; }
  const envelope = JSON.stringify({
    snapshot: snapshot,
    state_token: "f".repeat(64),
    operation_id: "o".repeat(80),
  });
  const limit = stage6TransferLimit;
  if (new Blob([envelope]).size > limit) {
    return { error: "This account file is larger than the current " + Math.round(limit / 1024) + " KiB transfer limit." };
  }
  const problem = transferSnapshotProblem(snapshot);
  return problem ? { error: problem } : { value: snapshot };
}

function transferCount(group) {
  return (group.added || []).length + (group.changed || []).length + (group.removed || []).length;
}

function renderTransferPreview(preview) {
  const changes = preview.changes || {};
  accessElement("account-import-source").textContent = "From " + preview.source_username +
    ". Review what will change in " + account.username + ".";
  const grid = accessElement("account-import-diff");
  grid.replaceChildren();
  [["Weeks", changes.weeks], ["Homework", changes.assignments], ["Routines", changes.routines]].forEach(function (entry) {
    const group = entry[1] || {};
    const count = transferCount(group);
    const card = document.createElement("section");
    const heading = document.createElement("strong");
    heading.textContent = entry[0] + ": " + count + " change" + (count === 1 ? "" : "s");
    const detail = document.createElement("span");
    detail.textContent = (group.added || []).length + " added · " + (group.changed || []).length +
      " changed · " + (group.removed || []).length + " removed";
    card.appendChild(heading);
    card.appendChild(detail);
    grid.appendChild(card);
  });
  const settings = document.createElement("section");
  const settingsHeading = document.createElement("strong");
  settingsHeading.textContent = "Settings: " + (changes.preferences_changed ? "will be replaced" : "no changes");
  const settingsDetail = document.createElement("span");
  settingsDetail.textContent = changes.preferences_changed
    ? "Settings are not covered by the automatic recovery point." : "The source and destination settings match.";
  settings.appendChild(settingsHeading);
  settings.appendChild(settingsDetail);
  grid.appendChild(settings);
  const removals = accessElement("account-import-removals");
  removals.replaceChildren();
  [["Week", changes.weeks], ["Homework", changes.assignments], ["Routine", changes.routines]]
    .forEach(function (entry) {
      (entry[1] && entry[1].removed || []).forEach(function (item) {
        const line = document.createElement("li");
        const label = typeof item === "string" ? item : (item.title || item.name || item.id);
        line.textContent = entry[0] + ": " + label;
        removals.appendChild(line);
      });
    });
  if (!removals.children.length) {
    const line = document.createElement("li");
    line.textContent = "Nothing will be removed.";
    removals.appendChild(line);
  }
  accessElement("account-import-ack").checked = false;
  accessElement("account-import-confirm").disabled = true;
  const panel = accessElement("account-import-preview");
  panel.hidden = false;
  // Appearing is silent: without a focus move the reader stays on the file button.
  if (typeof panel.focus === "function") panel.focus();
}

function resetTransferPreview() {
  stage6Import = null;
  accessElement("account-import-file").value = "";
  accessElement("account-import-preview").hidden = true;
  accessElement("account-import-ack").checked = false;
  accessElement("account-import-confirm").disabled = true;
  accessElement("account-import-diff").replaceChildren();
  accessElement("account-import-removals").replaceChildren();
}

async function previewTransferSnapshot(snapshot) {
  if (!account || stage6Busy) return false;
  const previewEpoch = epoch;
  const accountId = account.id;
  stage6Busy = true;
  accessError("transfer-error", "");
  try {
    const preview = await api("/api/account-import/preview", {
      method: "POST", body: JSON.stringify({ snapshot: snapshot }),
    });
    if (previewEpoch !== epoch || !account || account.id !== accountId) return false;
    stage6Import = { snapshot: snapshot, preview: preview, accountId: accountId,
      operationId: transferOperationId() };
    renderTransferPreview(preview);
    return true;
  } catch (error) {
    if (previewEpoch === epoch) accessError("transfer-error", "Nothing was imported. " + error.message);
    return false;
  } finally {
    stage6Busy = false;
  }
}

async function chooseTransferFile() {
  const file = accessElement("account-import-file").files && accessElement("account-import-file").files[0];
  accessElement("account-import-file").value = "";
  if (!file || !account) return;
  const fileEpoch = epoch;
  const accountId = account.id;
  let text;
  try { text = await file.text(); }
  catch (error) { accessError("transfer-error", "Could not read that file. " + error.message); return; }
  if (fileEpoch !== epoch || !account || account.id !== accountId) return;
  const parsed = parseTransferSnapshot(text);
  if (parsed.error) {
    resetTransferPreview();
    accessError("transfer-error", parsed.error + " Nothing was imported.");
    return;
  }
  await previewTransferSnapshot(parsed.value);
}

async function exportAccount(event) {
  event.preventDefault();
  if (!account || stage6Busy) return;
  if (accountHasUnsavedChanges()) {
    accessError("transfer-error", "Save, retry or download your unsaved changes before exporting the account.");
    return;
  }
  const form = event.currentTarget;
  const exportEpoch = epoch;
  const accountId = account.id;
  stage6Busy = true;
  setAccessFormBusy(form, true);
  accessError("transfer-error", "");
  try {
    const snapshot = await api("/api/account-export", { method: "POST", keepSessionOn401: true,
      body: JSON.stringify({ password: accessElement("account-export-password").value }) });
    if (exportEpoch !== epoch || !account || account.id !== accountId) return;
    downloadText("flexweek-account-" + account.username + "-" + snapshot.exported_at.slice(0, 10) + ".json",
      JSON.stringify(snapshot, null, 2), "application/json");
    accessElement("account-export-password").value = "";
    setStatus("Account file downloaded. Keep it private, then preview it in the destination account.");
  } catch (error) {
    if (exportEpoch === epoch) accessError("transfer-error", "Account file was not downloaded. " + error.message);
  } finally {
    stage6Busy = false;
    setAccessFormBusy(form, false);
  }
}

async function applyTransfer() {
  if (!stage6Import || !stage6Import.preview || !account || stage6Busy
      || !accessElement("account-import-ack").checked) return false;
  if (accountHasUnsavedChanges()) {
    accessError("transfer-error", "Save, retry or download your unsaved changes before importing.");
    return false;
  }
  const pending = stage6Import;
  const identity = { ...account };
  const applyEpoch = epoch;
  stage6Busy = true;
  accessElement("account-import-confirm").disabled = true;
  accessError("transfer-error", "");
  try {
    await api("/api/account-import", { method: "POST", body: JSON.stringify({
      snapshot: pending.snapshot, state_token: pending.preview.state_token, operation_id: pending.operationId,
    }) });
    if (applyEpoch !== epoch || !account || account.id !== pending.accountId) return false;
    resetTransferPreview();
    closeAccessDialog(accessElement("transfer-dialog"));
    clearHistory();
    await loadAccount(identity);
    if (account) setStatus("Account data imported. The destination now matches the previewed file.");
    return true;
  } catch (error) {
    if (applyEpoch !== epoch) return false;
    if (error.status === 409) {
      stage6Import = { snapshot: pending.snapshot, preview: null, accountId: pending.accountId, operationId: null };
      accessElement("account-import-ack").checked = false;
      accessElement("account-import-confirm").disabled = true;
      accessError("transfer-error", "The destination changed after this preview. Choose the file again and review a fresh preview. Nothing was imported.");
    } else {
      accessError("transfer-error", "Nothing was imported. " + error.message);
    }
    return false;
  } finally {
    stage6Busy = false;
    if (stage6Import && stage6Import.preview) {
      accessElement("account-import-confirm").disabled = !accessElement("account-import-ack").checked;
    }
  }
}

async function replaceRecoveryCodes(event) {
  event.preventDefault();
  if (!account || stage6Busy) return;
  const form = event.currentTarget;
  const requestEpoch = epoch;
  const accountId = account.id;
  stage6Busy = true;
  setAccessFormBusy(form, true);
  accessError("replace-codes-error", "");
  try {
    const result = await api("/api/auth/recovery-codes", { method: "POST", keepSessionOn401: true,
      body: JSON.stringify({ password: accessElement("replace-codes-password").value }) });
    if (requestEpoch !== epoch || !account || account.id !== accountId) return;
    form.reset();
    closeAccessDialog(accessElement("replace-codes-dialog"));
    renderRecoveryStatus(result.remaining);
    showRecoveryCodes(result.recovery_codes, false);
  } catch (error) {
    if (requestEpoch === epoch) accessError("replace-codes-error", error.message);
  } finally {
    stage6Busy = false;
    setAccessFormBusy(form, false);
  }
}

async function changeAccountPassword(event) {
  event.preventDefault();
  if (!account || stage6Busy) return;
  const current = accessElement("change-password-current");
  const next = accessElement("change-password-new");
  if (next.value !== accessElement("change-password-confirm").value) {
    accessError("change-password-error", "The new passwords do not match.");
    return;
  }
  const form = event.currentTarget;
  const requestEpoch = epoch;
  const accountId = account.id;
  stage6Busy = true;
  setAccessFormBusy(form, true);
  accessError("change-password-error", "");
  try {
    const identity = await api("/api/auth/password", { method: "POST", keepSessionOn401: true,
      body: JSON.stringify({ current_password: current.value, new_password: next.value }) });
    if (requestEpoch !== epoch || !account || account.id !== accountId) return;
    account = identity;
    form.reset();
    closeAccessDialog(accessElement("change-password-dialog"));
    channel?.postMessage("session-changed");
    setStatus("Password changed. Other devices were signed out.");
  } catch (error) {
    if (requestEpoch === epoch) accessError("change-password-error", error.message);
  } finally {
    stage6Busy = false;
    setAccessFormBusy(form, false);
  }
}

async function deleteAccount(event) {
  event.preventDefault();
  if (!account || stage6Busy) return;
  const expected = account.username;
  if (accessElement("delete-account-username").value !== expected) {
    accessError("delete-account-error", "Type " + expected + " exactly to confirm deletion.");
    return;
  }
  const form = event.currentTarget;
  const requestEpoch = epoch;
  const accountId = account.id;
  stage6Busy = true;
  setAccessFormBusy(form, true);
  accessError("delete-account-error", "");
  try {
    await api("/api/auth/account", { method: "DELETE", keepSessionOn401: true,
      body: JSON.stringify({ password: accessElement("delete-account-password").value }) });
    if (requestEpoch !== epoch || !account || account.id !== accountId) return;
    suspendedDrafts.delete(accountId);
    suspendedAssignments.delete(accountId);
    forgetFocus(accountId);
    form.reset();
    closeAccessDialog(accessElement("delete-account-dialog"));
    signedOut("Account deleted. You can create a new account with that username.", false, "register");
    channel?.postMessage("session-changed");
  } catch (error) {
    if (requestEpoch === epoch) accessError("delete-account-error", error.message);
  } finally {
    stage6Busy = false;
    setAccessFormBusy(form, false);
  }
}

function clearAccessState() {
  stage6ReferenceEpoch = null;
  stage6RecoveryCodes = [];
  stage6RegistrationCodes = false;
  stage6Import = null;
  stage6Busy = false;
  ["recovery-codes-dialog", "replace-codes-dialog", "change-password-dialog", "transfer-dialog",
    "delete-account-dialog"].forEach(function (id) { closeAccessDialog(accessElement(id)); });
  ["replace-codes-form", "change-password-form", "account-export-form", "delete-account-form"]
    .forEach(function (id) { accessElement(id).reset(); });
  accessElement("account-location-label").textContent = "Checking account location…";
  accessElement("prefs-account").textContent = "";
  accessElement("account-location-origin").textContent = "";
  accessElement("account-sync-note").textContent = "Checking how this account is shared…";
  accessElement("recovery-status").textContent = "Checking recovery codes…";
  renderRecoveryCodes();
  resetTransferPreview();
}

accessElement("recovery-codes-ack").addEventListener("change", function (event) {
  accessElement("recovery-codes-done").disabled = !event.currentTarget.checked;
});
accessElement("recovery-codes-copy").addEventListener("click", copyRecoveryCodes);
accessElement("recovery-codes-download").addEventListener("click", downloadRecoveryCodes);
accessElement("recovery-codes-done").addEventListener("click", finishRecoveryCodes);
accessElement("recovery-codes-dialog").addEventListener("cancel", function (event) { event.preventDefault(); });
accessElement("recovery-codes-open").addEventListener("click", function () {
  if (!account) return;
  accessElement("replace-codes-form").reset();
  accessError("replace-codes-error", "");
  openAccessDialog(accessElement("replace-codes-dialog"));
});
accessElement("replace-codes-form").addEventListener("submit", replaceRecoveryCodes);
accessElement("replace-codes-cancel").addEventListener("click", function () {
  closeAccessDialog(accessElement("replace-codes-dialog"));
});
accessElement("change-password-open").addEventListener("click", function () {
  if (!account) return;
  accessElement("change-password-form").reset();
  accessError("change-password-error", "");
  openAccessDialog(accessElement("change-password-dialog"));
});
accessElement("change-password-form").addEventListener("submit", changeAccountPassword);
accessElement("change-password-cancel").addEventListener("click", function () {
  closeAccessDialog(accessElement("change-password-dialog"));
});
accessElement("transfer-open").addEventListener("click", openTransferDialog);
accessElement("account-export-form").addEventListener("submit", exportAccount);
accessElement("account-import-choose").addEventListener("click", function () {
  accessElement("account-import-file").click();
});
accessElement("account-import-file").addEventListener("change", chooseTransferFile);
accessElement("account-import-ack").addEventListener("change", function (event) {
  accessElement("account-import-confirm").disabled = !event.currentTarget.checked || !stage6Import || !stage6Import.preview;
});
accessElement("account-import-confirm").addEventListener("click", applyTransfer);
accessElement("transfer-close").addEventListener("click", function () {
  resetTransferPreview();
  closeAccessDialog(accessElement("transfer-dialog"));
});
accessElement("delete-account-open").addEventListener("click", function () {
  if (!account) return;
  accessElement("delete-account-form").reset();
  accessElement("delete-account-username-label").textContent = account.username;
  accessError("delete-account-error", "");
  openAccessDialog(accessElement("delete-account-dialog"));
});
accessElement("delete-account-form").addEventListener("submit", deleteAccount);
accessElement("delete-account-cancel").addEventListener("click", function () {
  closeAccessDialog(accessElement("delete-account-dialog"));
});
accessElement("prefs-open").addEventListener("click", prepareStage6Account);
