(() => {
  const formatDisplayDate = (isoDate) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate || "");
    return match ? `${match[3]}/${match[2]}/${match[1]}` : "";
  };

  document.querySelectorAll("[data-date-picker]").forEach((picker) => {
    const input = picker.querySelector("[data-date-input]");
    const display = picker.querySelector("[data-date-display]");
    const button = picker.querySelector("[data-date-button]");
    const syncDisplay = () => {
      display.value = formatDisplayDate(input.value);
    };
    const openPicker = () => {
      if (typeof input.showPicker === "function") {
        input.showPicker();
      } else {
        input.focus();
        input.click();
      }
    };

    input.addEventListener("input", syncDisplay);
    input.addEventListener("change", syncDisplay);
    button.addEventListener("click", openPicker);
    syncDisplay();
  });
})();
