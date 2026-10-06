import { renderText } from "./render.js";

export function createRowMenu(owner) {
  const document = owner.ownerDocument;
  const view = document.defaultView;
  const menu = document.createElement("div");
  menu.className = "nami-menu nami-row-menu";
  menu.setAttribute("role", "menu");
  menu.ariaLabel = "Item actions";
  menu.hidden = true;
  owner.append(menu);
  let current = null;

  function close(restore = false) {
    const previous = current;
    current = null;
    menu.hidden = true;
    document.removeEventListener("pointerdown", outside);
    document.removeEventListener("scroll", scrolled, true);
    document.removeEventListener("visibilitychange", foreground);
    view.removeEventListener("blur", dismiss);
    view.removeEventListener("resize", dismiss);
    if (restore && previous?.isCurrent()) previous.returnFocus.focus();
  }
  function dismiss() { close(); }
  function outside(event) { if (!menu.contains(event.target)) close(); }
  function scrolled(event) { if (!menu.contains(event.target)) close(); }
  function foreground() { if (document.hidden) close(); }
  function reconcile() { if (current !== null && !current.isCurrent()) close(); }

  function open(event, anchor, returnFocus, actions, isCurrent) {
    close();
    event.preventDefault();
    event.stopPropagation();
    if (!isCurrent() || actions.length === 0) return;
    const context = { returnFocus, isCurrent };
    current = context;
    menu.replaceChildren();
    for (const action of actions) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "nami-menu__item";
      item.setAttribute("role", "menuitem");
      item.tabIndex = -1;
      item.dataset.action = action.id;
      renderText(item, action.label);
      item.addEventListener("click", () => {
        if (current !== context || !isCurrent()) { reconcile(); return; }
        close(true);
        action.run();
      });
      menu.append(item);
    }
    menu.hidden = false;
    const boundary = owner.closest(".nami-work-panel")?.getBoundingClientRect();
    const left = Math.max(8, boundary?.left ?? 8);
    const top = Math.max(8, boundary?.top ?? 8);
    const right = Math.min(view.innerWidth - 8, boundary?.right ?? view.innerWidth - 8);
    const bottom = Math.min(view.innerHeight - 8, boundary?.bottom ?? view.innerHeight - 8);
    menu.style.setProperty("max-inline-size", `${right - left}px`);
    menu.style.setProperty("max-block-size", `${bottom - top}px`);
    const bounds = menu.getBoundingClientRect();
    const rect = anchor.getBoundingClientRect();
    const keyboard = event.type === "keydown";
    const x = keyboard ? rect.left : event.clientX;
    const y = keyboard ? rect.bottom : event.clientY;
    menu.style.setProperty("left", `${Math.max(left, Math.min(x, right - bounds.width))}px`);
    menu.style.setProperty("top", `${Math.max(top, Math.min(y, bottom - bounds.height))}px`);
    document.addEventListener("pointerdown", outside);
    document.addEventListener("scroll", scrolled, true);
    document.addEventListener("visibilitychange", foreground);
    view.addEventListener("blur", dismiss);
    view.addEventListener("resize", dismiss);
    menu.children[0].focus();
  }
  menu.addEventListener("focusout", (event) => {
    if (!menu.contains(event.relatedTarget)) close();
  });
  menu.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    event.stopPropagation();
  });
  menu.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "Tab") {
      close(true);
    } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const items = [...menu.children];
      const index = items.indexOf(document.activeElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
        : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      items[next].focus();
    }
  });
  return Object.freeze({ open, close, reconcile, dispose: close });
}
