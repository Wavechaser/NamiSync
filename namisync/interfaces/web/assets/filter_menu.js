import { createIcon } from "./icons.js";
import { renderText } from "./render.js";

export function createFilterMenu(categories, onChange) {
  const root = document.createElement("div");
  root.className = "nami-filter-menu";
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "nami-button nami-filter-menu__trigger";
  trigger.dataset.action = "filter-menu";
  trigger.ariaHasPopup = "menu";
  trigger.ariaExpanded = "false";
  const caption = document.createElement("span");
  renderText(caption, "Filter");
  const activeCount = document.createElement("span");
  activeCount.className = "nami-filter-count";
  trigger.append(createIcon(document, "filter", "sm"), caption, activeCount,
    createIcon(document, "chevron-down", "sm"));
  const menu = document.createElement("div");
  menu.className = "nami-menu nami-filter-menu__popup";
  menu.setAttribute("role", "menu");
  menu.ariaLabel = "Filter categories";
  menu.hidden = true;
  root.append(trigger, menu);
  const items = new Map();
  let selected = new Set();
  let disabled = true;
  const view = document.defaultView;

  for (const [key, label] of [["all", "All"], ...categories]) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "nami-menu__item nami-filter-menu__item";
    item.setAttribute("role", "menuitemcheckbox");
    item.tabIndex = -1;
    item.dataset.filter = key;
    const check = createIcon(document, "checkmark", "sm");
    check.classList.add("nami-filter-menu__check");
    const text = document.createElement("span");
    renderText(text, label);
    const count = document.createElement("span");
    count.className = "nami-filter-count";
    item.append(check, text, count);
    item.addEventListener("click", () => {
      if (disabled) return;
      const next = new Set(selected);
      if (key === "all") next.clear();
      else if (next.has(key)) next.delete(key);
      else next.add(key);
      onChange(next);
    });
    items.set(key, item);
    menu.append(item);
  }

  function close() {
    menu.hidden = true;
    trigger.ariaExpanded = "false";
    document.removeEventListener("pointerdown", outside);
    document.removeEventListener("visibilitychange", foreground);
    document.removeEventListener("scroll", outside, true);
    view.removeEventListener("blur", close);
    view.removeEventListener("resize", close);
  }
  function outside(event) { if (!root.contains(event.target)) close(); }
  function foreground() { if (document.hidden) close(); }
  function open(last = false) {
    if (disabled) return;
    menu.hidden = false;
    trigger.ariaExpanded = "true";
    const rect = trigger.getBoundingClientRect();
    const boundary = root.closest(".nami-work-panel")?.getBoundingClientRect();
    const top = Math.max(0, boundary?.top ?? 0);
    const bottom = Math.min(view.innerHeight, boundary?.bottom ?? view.innerHeight);
    const below = bottom - rect.bottom - 8;
    const above = rect.top - top - 8;
    const upwards = below < 240 && above > below;
    menu.style.setProperty("inset-block-start", upwards ? "auto" : "calc(100% + var(--space-1))");
    menu.style.setProperty("inset-block-end", upwards ? "calc(100% + var(--space-1))" : "auto");
    menu.style.setProperty("max-block-size", `${Math.max(32, Math.min(384, upwards ? above : below))}px`);
    document.addEventListener("pointerdown", outside);
    document.addEventListener("visibilitychange", foreground);
    document.addEventListener("scroll", outside, true);
    view.addEventListener("blur", close);
    view.addEventListener("resize", close);
    const options = [...items.values()];
    options[last ? options.length - 1 : 0].focus();
  }
  trigger.addEventListener("click", () => { if (menu.hidden) open(); else close(); });
  trigger.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      open(event.key === "ArrowUp");
    }
  });
  root.addEventListener("focusout", (event) => { if (!root.contains(event.relatedTarget)) close(); });
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      trigger.focus();
    } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const options = [...items.values()];
      const index = options.indexOf(document.activeElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1
        : (index + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      options[next].focus();
    }
  });

  function render(filters, counts, pending) {
    selected = new Set(filters);
    disabled = pending;
    trigger.ariaDisabled = String(disabled);
    trigger.dataset.active = String(selected.size > 0);
    trigger.ariaLabel = `Filter ${selected.size} active categories`;
    renderText(activeCount, String(selected.size));
    for (const [key, item] of items) {
      item.ariaChecked = String(key === "all" ? selected.size === 0 : selected.has(key));
      item.ariaDisabled = String(disabled);
      const count = counts[key];
      renderText(item.children[2], count === undefined ? "" : String(count));
      item.children[2].hidden = count === undefined;
      item.ariaLabel = `${item.children[1].textContent}${count === undefined ? "" : ` ${count}`}`;
    }
  }
  render([], {}, true);
  return Object.freeze({ element: root, render, close, dispose: close });
}
