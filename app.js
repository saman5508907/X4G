function copyReminder() {
  const field = document.getElementById("reminderText");
  if (!field) return;
  navigator.clipboard.writeText(field.value).then(() => {
    const status = document.getElementById("copyStatus");
    if (status) status.textContent = "Copied to clipboard";
  }).catch(() => {
    field.select();
    document.execCommand("copy");
    const status = document.getElementById("copyStatus");
    if (status) status.textContent = "Copied";
  });
}
