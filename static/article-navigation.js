(() => {
  "use strict";

  const navigation = document.getElementById("keyboard-article-navigation");
  if (!navigation) return;

  const isEditing = (target) => {
    if (!(target instanceof Element)) return false;
    return Boolean(
      target.closest("input, textarea, select, button, [contenteditable='true']")
    );
  };

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.repeat || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
      return;
    }
    if (isEditing(event.target)) return;

    let destination = "";
    if (event.key === "ArrowLeft") {
      destination = navigation.dataset.previousUrl || "";
    } else if (event.key === "ArrowRight") {
      destination = navigation.dataset.nextUrl || "";
    }

    if (destination) {
      event.preventDefault();
      window.location.assign(destination);
    }
  });
})();
