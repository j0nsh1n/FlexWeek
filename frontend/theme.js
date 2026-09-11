// Theme choice. "system" follows the device's light or dark setting and switches
// when it changes; "slate" (Light) and "nocturne" (Dark) stay put. The stylesheet
// only knows the two resolved names on <html data-theme>. This script runs in
// <head>, before the body exists, so the first paint already matches the device.
const systemDark = typeof matchMedia === "function" ? matchMedia("(prefers-color-scheme: dark)") : null;
let themeChoice = "system";

function resolvedTheme(choice) {
  if (choice === "slate" || choice === "nocturne") return choice;
  return systemDark && systemDark.matches ? "nocturne" : "slate";
}

function applyTheme(choice) {
  themeChoice = choice === "slate" || choice === "nocturne" ? choice : "system";
  document.documentElement.dataset.theme = resolvedTheme(themeChoice);
}

if (systemDark && typeof systemDark.addEventListener === "function") {
  systemDark.addEventListener("change", function () {
    if (themeChoice === "system") applyTheme("system");
  });
}

applyTheme("system");
