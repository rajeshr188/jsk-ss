"use strict";

const pwaScript = document.currentScript;
const pwaEnabled = pwaScript?.dataset.pwaEnabled === "true";

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    if (pwaEnabled) {
      navigator.serviceWorker.register("/service-worker.js", {
        scope: "/",
        updateViaCache: "none",
      }).catch(() => {
        // Installation is optional; the online Django application remains usable.
      });
      return;
    }

    // A rollback/disable must retire this app's existing worker and reviewed cache
    // on the next successful online page load without touching another worker.
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      registrations.forEach((registration) => {
        const worker = registration.active || registration.waiting || registration.installing;
        if (worker?.scriptURL.endsWith("/service-worker.js")) {
          registration.unregister();
        }
      });
    });
    if ("caches" in window) {
      caches.keys().then((names) => {
        names
          .filter((name) => name.startsWith("jsk-pwa-static-"))
          .forEach((name) => caches.delete(name));
      });
    }
  });
}
