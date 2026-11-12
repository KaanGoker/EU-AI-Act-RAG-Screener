// Runs before first paint: apply the remembered theme, if any.
(function () {
  try {
    var t = localStorage.getItem("screener-theme");
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* storage blocked: follow the system */ }
})();
