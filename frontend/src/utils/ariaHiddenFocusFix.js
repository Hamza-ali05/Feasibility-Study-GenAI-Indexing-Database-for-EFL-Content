/**
 * Chrome warns when MUI Modal/Dialog sets aria-hidden on #app while a
 * descendant (e.g. the button that opened the dialog) still has focus.
 * Blur that element so assistive tech is not pointed at a hidden node.
 */
export function installAriaHiddenFocusFix(rootId = "app") {
  if (typeof window === "undefined" || typeof MutationObserver === "undefined") {
    return () => {};
  }

  const blurHiddenFocus = () => {
    const root = document.getElementById(rootId);
    if (!root || root.getAttribute("aria-hidden") !== "true") return;
    const active = document.activeElement;
    if (active instanceof HTMLElement && root.contains(active)) {
      active.blur();
    }
  };

  const observer = new MutationObserver((mutations) => {
    for (let i = 0; i < mutations.length; i += 1) {
      const mutation = mutations[i];
      if (mutation.type === "attributes" && mutation.attributeName === "aria-hidden") {
        blurHiddenFocus();
        break;
      }
    }
  });

  const attach = () => {
    const root = document.getElementById(rootId);
    if (!root) return false;
    observer.observe(root, { attributes: true, attributeFilter: ["aria-hidden"] });
    blurHiddenFocus();
    return true;
  };

  if (!attach()) {
    // Root may not exist yet during first paint.
    requestAnimationFrame(attach);
  }

  return () => observer.disconnect();
}
