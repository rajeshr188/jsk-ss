// Keep location/keyboard context clear and give payment submission feedback.
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-payment-submission]").forEach(form => {
    form.addEventListener("submit", event => {
      if (form.dataset.submitting === "true") { event.preventDefault(); return; }
      form.dataset.submitting = "true";
      const button = form.querySelector("button[type='submit']");
      button.dataset.originalText = button.textContent;
      button.disabled = true;
      button.textContent = "Opening secure payment…";
      form.setAttribute("aria-busy", "true");
    });
  });
  document.querySelectorAll(".workspace-nav-link, .customer-navigation a").forEach(link => {
    if (new URL(link.href).pathname === location.pathname) link.setAttribute("aria-current", "page");
  });
  const invalid = document.querySelector(".is-invalid, [aria-invalid='true']");
  const target = invalid || document.querySelector("form .alert-danger, form .errorlist");
  if (target) {
    let disclosure = target.closest("details");
    while (disclosure) { disclosure.open = true; disclosure = disclosure.parentElement.closest("details"); }
    if (!invalid) target.setAttribute("tabindex", "-1");
    target.focus();
  }
});
window.addEventListener("pageshow", () => {
  document.querySelectorAll("form[data-payment-submission]").forEach(form => {
    delete form.dataset.submitting;
    form.removeAttribute("aria-busy");
    const button = form.querySelector("button[type='submit']");
    button.disabled = false;
    if (button.dataset.originalText) button.textContent = button.dataset.originalText;
  });
});
