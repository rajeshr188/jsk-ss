// Read-only fragments. No logging, storage, provider calls or mutation retries.
(() => {
  let pageNavigation = false;
  document.addEventListener("htmx:beforeRequest", event => {
    pageNavigation = event.detail.elt.hasAttribute("data-page-link") || event.detail.elt.matches("form[data-read-filter]");
    document.querySelectorAll("[data-read-error]").forEach(node => { node.textContent = ""; });
    if (event.detail.target) event.detail.target.setAttribute("aria-busy", "true");
  });
  document.addEventListener("htmx:afterRequest", event => {
    if (event.detail.target) event.detail.target.removeAttribute("aria-busy");
    if (event.detail.successful) document.querySelectorAll("[data-read-error]").forEach(node => { node.textContent = ""; });
    if (event.detail.failed) {
      const message = document.querySelector("[data-read-error]");
      if (message) message.textContent = "Could not update this view. Your previous view is unchanged. Retry or reload the page.";
    }
  });
  document.addEventListener("htmx:afterSwap", event => {
    const current = document.getElementById(event.detail.target.id);
    if (current && (pageNavigation || current.id === "payment-status-panel")) current.focus({preventScroll: false});
    pageNavigation = false;
  });
})();
