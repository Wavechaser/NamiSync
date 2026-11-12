import { NAMI_LICENSE, OPEN_SOURCE_ACKNOWLEDGEMENTS } from "./legal_content.js";
import { renderText } from "./render.js";

export function installAboutNotices(root, backgroundRoots) {
  const notices = createAboutNotices(backgroundRoots);
  root.querySelector("#about-license").addEventListener("click", (event) => {
    notices.showLicense(event.currentTarget);
  });
  root.querySelector("#about-acknowledgements").addEventListener("click", (event) => {
    notices.showAcknowledgements(event.currentTarget);
  });
  return notices;
}

export function createAboutNotices(backgroundRoots) {
  if (!Array.isArray(backgroundRoots) || backgroundRoots.length === 0
      || !backgroundRoots.every((root) => root instanceof HTMLElement)) {
    throw new TypeError("About notices require page background roots");
  }
  const dialog = document.createElement("dialog");
  dialog.className = "nami-dialog nami-about-dialog";
  dialog.id = "about-notice-dialog";
  dialog.setAttribute("aria-labelledby", "about-notice-title");
  const heading = document.createElement("h2");
  heading.id = "about-notice-title";
  const body = document.createElement("div");
  body.className = "nami-about-dialog__body";
  body.tabIndex = 0;
  body.setAttribute("role", "region");
  body.setAttribute("aria-labelledby", heading.id);
  const actions = document.createElement("div");
  actions.className = "nami-about-dialog__actions";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "nami-button nami-button--primary";
  renderText(close, "Close");
  actions.append(close);
  dialog.append(heading, body, actions);
  let current = null;

  function restoreBackground(state) {
    for (const [root, inert] of state.background) root.inert = inert;
    const [value, priority] = state.overflow;
    if (value === "") document.documentElement.style.removeProperty("overflow");
    else document.documentElement.style.setProperty("overflow", value, priority);
  }

  function finishClose(state) {
    if (current !== state) return;
    dialog.close();
    delete dialog.dataset.closing;
    current = null;
    restoreBackground(state);
    if (state.returnFocus.isConnected && !state.returnFocus.disabled) state.returnFocus.focus();
  }

  function dismiss() {
    const state = current;
    if (state === null || state.closing) return;
    state.closing = true;
    close.disabled = true;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (current !== state) return;
      dialog.dataset.closing = "true";
      const animations = dialog.getAnimations().filter((animation) =>
        Number.isFinite(animation.effect?.getComputedTiming().endTime));
      if (animations.length === 0) {
        requestAnimationFrame(() => finishClose(state));
      } else {
        void Promise.allSettled(animations.map((animation) => animation.finished))
          .then(() => finishClose(state));
      }
    }));
  }

  close.addEventListener("click", dismiss);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    dismiss();
  });
  for (const name of ["pointerdown", "pointerup", "click", "dblclick", "contextmenu", "wheel"]) {
    dialog.addEventListener(name, (event) => {
      if (event.target !== dialog) return;
      event.preventDefault();
      event.stopPropagation();
    });
  }

  function paragraph(text, className = "") {
    const element = document.createElement("p");
    element.className = className;
    renderText(element, text);
    return element;
  }

  function notice(record, title = null) {
    const section = document.createElement("section");
    section.className = "nami-about-dialog__notice";
    if (title !== null) {
      const subheading = document.createElement("h3");
      renderText(subheading, title);
      section.append(subheading);
    }
    section.append(paragraph(record.license), paragraph(record.source, "nami-about-dialog__source"));
    if (record.note) section.append(paragraph(record.note));
    const text = document.createElement("pre");
    renderText(text, record.text);
    section.append(text);
    return section;
  }

  function show(title, contents, returnFocus) {
    if (current !== null) return;
    if (!(returnFocus instanceof HTMLElement)) throw new TypeError("About notices require an invoking control");
    renderText(heading, title);
    body.replaceChildren(...contents);
    body.scrollTop = 0;
    const state = {
      returnFocus, closing: false,
      background: backgroundRoots.map((root) => [root, root.inert]),
      overflow: [document.documentElement.style.getPropertyValue("overflow"),
        document.documentElement.style.getPropertyPriority("overflow")],
    };
    current = state;
    document.documentElement.style.setProperty("overflow", "hidden", "important");
    for (const root of backgroundRoots) root.inert = true;
    close.disabled = false;
    delete dialog.dataset.closing;
    try {
      dialog.showModal();
    } catch (error) {
      current = null;
      restoreBackground(state);
      throw error;
    }
    close.focus();
  }

  return Object.freeze({
    element: dialog,
    showLicense(returnFocus) {
      show(NAMI_LICENSE.title, [notice(NAMI_LICENSE)], returnFocus);
    },
    showAcknowledgements(returnFocus) {
      const content = OPEN_SOURCE_ACKNOWLEDGEMENTS;
      show(content.title, [paragraph(content.scope),
        ...content.notices.map((record) => notice(record, `${record.name} ${record.version}`))], returnFocus);
    },
  });
}
