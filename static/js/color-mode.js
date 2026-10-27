// Apply before styles load; only a display preference is stored on this device.
(() => {
  "use strict";
  const key = "jsk-color-mode";
  const valid = value => ["light", "dark", "system"].includes(value) ? value : "system";
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";
  try { preference = valid(localStorage.getItem(key)); } catch (_) { /* Storage may be blocked. */ }

  function apply() {
    const mode = preference === "system" ? (system.matches ? "dark" : "light") : preference;
    document.documentElement.dataset.bsTheme = mode;
    const chrome = document.querySelector('meta[name="theme-color"]');
    if (chrome) chrome.content = mode === "dark" ? "#191715" : "#2d1811";
    document.querySelectorAll("[data-color-mode]").forEach(control => {
      control.hidden = false;
      const label = preference.charAt(0).toUpperCase() + preference.slice(1);
      control.querySelector(".color-mode-toggle").setAttribute("aria-label", `Color mode: ${label}`);
      control.querySelectorAll("[data-theme-choice]").forEach(button => {
        const selected = button.dataset.themeChoice === preference;
        button.setAttribute("aria-pressed", String(selected));
        button.classList.toggle("active", selected);
        button.querySelector("[data-theme-check]").hidden = !selected;
      });
    });
  }
  apply();
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-theme-choice]").forEach(button => {
      button.addEventListener("click", () => {
        preference = valid(button.dataset.themeChoice);
        try { localStorage.setItem(key, preference); } catch (_) { /* Keep this tab usable. */ }
        apply();
      });
    });
    apply();
  });
  system.addEventListener("change", () => { if (preference === "system") apply(); });
  window.addEventListener("storage", event => {
    if (event.key === key || event.key === null) {
      preference = valid(event.newValue);
      apply();
    }
  });
})();
