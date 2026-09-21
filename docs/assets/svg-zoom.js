// Inline SVG diagrams draw with currentColor so they follow the light/dark
// theme. glightbox only opens <img>, and an <img> cannot inherit that color, so
// this clones the inline <svg> into an overlay instead.
//
// Click a diagram: it fills the screen. Click again: 2x, scroll to pan.
// Esc or a click on the backdrop closes it.
(function () {
  function close(overlay) {
    overlay.remove();
    document.body.classList.remove("svg-zoom-open");
  }

  function open(svg) {
    const overlay = document.createElement("div");
    overlay.className = "svg-zoom-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-label", svg.getAttribute("aria-label") || "diagram");

    const frame = document.createElement("div");
    frame.className = "svg-zoom-frame";
    const clone = svg.cloneNode(true);
    clone.removeAttribute("style");
    frame.appendChild(clone);
    overlay.appendChild(frame);

    const hint = document.createElement("div");
    hint.className = "svg-zoom-hint";
    hint.textContent = "Click: 2x · Esc: close";
    overlay.appendChild(hint);

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) return close(overlay);
      frame.classList.toggle("is-2x");
    });
    const onKey = (e) => {
      if (e.key === "Escape") {
        close(overlay);
        document.removeEventListener("keydown", onKey);
      }
    };
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    document.body.classList.add("svg-zoom-open");
  }

  function bind() {
    document.querySelectorAll(".md-content figure > svg").forEach((svg) => {
      if (svg.dataset.zoomBound) return;
      svg.dataset.zoomBound = "1";
      svg.classList.add("svg-zoomable");
      svg.addEventListener("click", () => open(svg));
    });
  }

  // Material's instant navigation swaps pages without a reload; document$
  // fires on every swap, so diagrams on the new page get bound too.
  if (window.document$) window.document$.subscribe(bind);
  else document.addEventListener("DOMContentLoaded", bind);
})();
