(() => {
  const form = document.querySelector("[data-reset-form]");
  const loading = document.querySelector("[data-reset-loading]");
  const invalid = document.querySelector("[data-reset-invalid]");
  const requestLink = document.querySelector("[data-reset-request-link]");
  const tokenInput = form?.querySelector('input[name="token"]');
  if (!(form instanceof HTMLFormElement) || !(tokenInput instanceof HTMLInputElement)) return;

  const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  if (loading) loading.hidden = true;

  if (token && token.length >= 20 && token.length <= 200) {
    tokenInput.value = token;
    form.hidden = false;
  } else {
    if (invalid) invalid.hidden = false;
    if (requestLink) requestLink.hidden = false;
  }
})();
