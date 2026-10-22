// Keep location and keyboard context clear without intercepting form submissions.
document.addEventListener("DOMContentLoaded", () => {
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
