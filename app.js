document.addEventListener("click", async (event) => {
  const copyButton = event.target.closest("[data-copy]");
  if (copyButton) {
    const field = document.querySelector(copyButton.dataset.copy);
    if (!field) return;
    try {
      await navigator.clipboard.writeText(field.value);
      const old = copyButton.textContent;
      copyButton.textContent = "Copied!";
      setTimeout(() => copyButton.textContent = old, 1600);
    } catch {
      field.focus(); field.select();
      document.execCommand("copy");
      copyButton.textContent = "Copied!";
    }
  }
});
document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-confirm]");
  if (form && !window.confirm(form.dataset.confirm)) event.preventDefault();
});
