export function createTableController(viewport, rowHeight, topInset, callbacks) {
  const document = viewport.ownerDocument;
  const view = document.defaultView;
  let generation = 0;
  let total = 0;
  let offset = 0;
  let end = 0;
  let pending = null;
  let settled = null;
  let observedTop = viewport.scrollTop;
  let direction = 0;
  let expectedScroll = null;
  let manualScroll = false;
  let framePending = false;
  let disposed = false;

  const height = () => Math.max(0, viewport.clientHeight - topInset);
  function bounds(full = false) {
    const top = Math.max(0, viewport.scrollTop);
    return full
      ? [Math.ceil(top / rowHeight), Math.floor((top + height()) / rowHeight) - 1]
      : [Math.min(Math.floor(top / rowHeight), total - 1),
        Math.min(Math.max(Math.ceil((top + height()) / rowHeight) - 1,
          Math.floor(top / rowHeight)), total - 1)];
  }
  function clearPending() { pending = null; }
  function cancelPending() {
    const cancelled = pending?.generation;
    clearPending();
    if (cancelled !== undefined) callbacks.requestCancelled?.(cancelled);
  }
  function resetTravel() {
    direction = 0;
    observedTop = viewport.scrollTop;
  }
  function invalidate() { generation += 1; cancelPending(); }
  function reset() {
    generation += 1;
    clearPending();
    total = 0;
    offset = 0;
    end = 0;
    settled = null;
    resetTravel();
  }
  function beginRequest(index, kind) {
    generation += 1;
    cancelPending();
    settled = null;
    pending = Object.freeze({generation, index, kind, direction,
      scrollTop: kind === "scroll" ? viewport.scrollTop : null,
      clientHeight: kind === "scroll" ? height() : null});
    return generation;
  }
  function beginWindowRequest(index = null) {
    if (disposed) throw new Error("table controller is disposed");
    resetTravel();
    return beginRequest(index, "external");
  }
  function finishWindowRequest(requestGeneration, outcome) {
    if (disposed || requestGeneration !== generation || pending?.generation !== requestGeneration) return false;
    const request = pending;
    clearPending();
    settled = outcome === "retired" || outcome === "changed" || height() <= 0 ? null
      : request.kind === "scroll" ? request
        : {scrollTop: viewport.scrollTop, clientHeight: height()};
    if (outcome === "changed" || (outcome !== "retired" &&
        (settled?.scrollTop !== viewport.scrollTop || settled?.clientHeight !== height()))) schedule();
    return true;
  }
  function overlaps(window) {
    return height() > 0 && window.offset * rowHeight < viewport.scrollTop + height()
      && (window.offset + window.rows.length) * rowHeight > viewport.scrollTop;
  }
  function acceptsWindow(requestGeneration, window) {
    return !disposed && requestGeneration === generation
      && (pending?.kind !== "scroll" || height() <= 0 || overlaps(window));
  }
  function adoptWindow(window) {
    total = window.total;
    offset = Math.min(window.offset, total);
    end = offset + window.rows.length;
    settled = null;
  }
  function setWindow(window) {
    // External publications retire panel demand; their app still owns the read.
    if (window.total === 0) reset();
    adoptWindow(window);
    schedule();
  }
  function commitWindow(requestGeneration, window, paint, reveal = true) {
    if (disposed || requestGeneration !== generation) return false;
    const request = pending;
    if (!acceptsWindow(requestGeneration, window)) {
      finishWindowRequest(requestGeneration);
      return false;
    }
    const preservedTop = viewport.scrollTop;
    adoptWindow(window);
    clearPending();
    paint(request, () => {
      if (request?.kind === "scroll" || !reveal) setScrollTop(preservedTop, false);
    });
    if (request?.kind === "scroll" && viewport.scrollTop === request.scrollTop
        && height() === request.clientHeight) settled = request;
    else schedule();
    return true;
  }
  function requestWindow(index, kind, start = Math.max(0, index - 32)) {
    if (kind === "scroll" && pending?.kind === "scroll" && pending.direction === direction) return;
    const requestGeneration = beginRequest(index, kind);
    try { callbacks.requestIndex(index, requestGeneration, start); }
    catch (error) {
      if (pending?.generation === requestGeneration) clearPending();
      throw error;
    }
  }
  function requestKeyboard(index) { resetTravel(); requestWindow(index, "keyboard"); }
  function invalidateInternalRequest() {
    if (pending?.kind === "keyboard" || pending?.kind === "scroll") invalidate();
  }
  function cancelNavigation() { if (pending?.kind === "keyboard") invalidate(); }
  function setScrollTop(value, reconcile = true) {
    const previous = viewport.scrollTop;
    viewport.scrollTop = value;
    if (reconcile) resetTravel();
    if (viewport.scrollTop !== previous) expectedScroll = {reconcile, scrollTop: viewport.scrollTop};
  }
  function revealRow(index) {
    if (height() <= 0) return;
    const top = index * rowHeight;
    if (top < viewport.scrollTop) setScrollTop(top);
    else if (top + rowHeight > viewport.scrollTop + height()) setScrollTop(Math.max(0, top + rowHeight - height()));
  }
  function markManualScroll() { manualScroll = true; cancelNavigation(); }
  function onKeyDown(event) {
    if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(event.key)) manualScroll = true;
  }
  function onScroll() {
    if (expectedScroll !== null && viewport.scrollTop === expectedScroll.scrollTop) {
      const reconcile = expectedScroll.reconcile;
      expectedScroll = null;
      observedTop = viewport.scrollTop;
      manualScroll = false;
      if (!reconcile) return;
    } else {
      expectedScroll = null;
      const travel = Math.sign(viewport.scrollTop - observedTop);
      if (travel !== 0) direction = travel;
      observedTop = viewport.scrollTop;
      cancelNavigation();
      if (manualScroll) callbacks.manualScroll?.(...bounds());
      manualScroll = false;
    }
    schedule();
  }
  function schedule() {
    if (disposed || framePending) return;
    framePending = true;
    view.requestAnimationFrame(() => {
      framePending = false;
      if (!disposed) reconcileViewport();
    });
  }
  function reconcileViewport() {
    if (height() <= 0 || total <= 0) {
      resetTravel();
      settled = null;
      if (pending?.kind === "scroll") invalidate();
      return;
    }
    if (settled?.scrollTop === viewport.scrollTop && settled.clientHeight === height()) return;
    settled = null;
    if (pending?.kind === "external") { callbacks.viewportChanged?.(); return; }
    if (pending?.kind === "keyboard") return;
    const [first, last] = bounds();
    const covered = first >= offset && last < end;
    const travel = direction || (first < offset ? -1 : 1);
    const start = Math.min(total - 1, Math.max(0,
      travel < 0 ? last + 1 + 32 - 256 : first - 32));
    const advancing = travel < 0 ? start < offset : start > offset;
    const nearEdge = direction !== 0 && (travel < 0
      ? offset > 0 && first - offset <= 64 : end < total && end - last - 1 <= 64);
    callbacks.viewportChanged?.();
    if (covered && (!nearEdge || !advancing)) {
      if (pending?.kind === "scroll") invalidate();
      return;
    }
    if (start === offset && (end - offset >= 256 || end >= total)) return;
    requestWindow(first < offset ? first : last, "scroll", start);
  }
  viewport.addEventListener("scroll", onScroll, {passive: true});
  viewport.addEventListener("pointerdown", markManualScroll);
  viewport.addEventListener("wheel", markManualScroll, {passive: true});
  viewport.addEventListener("touchstart", markManualScroll, {passive: true});
  viewport.addEventListener("keydown", onKeyDown);
  const resizeObserver = new document.defaultView.ResizeObserver(schedule);
  resizeObserver.observe(viewport);
  function dispose() {
    if (disposed) return;
    disposed = true;
    invalidate();
    resizeObserver.disconnect();
    viewport.removeEventListener("scroll", onScroll);
    viewport.removeEventListener("pointerdown", markManualScroll);
    viewport.removeEventListener("wheel", markManualScroll);
    viewport.removeEventListener("touchstart", markManualScroll);
    viewport.removeEventListener("keydown", onKeyDown);
  }
  return Object.freeze({beginWindowRequest, finishWindowRequest, acceptsWindow, setWindow,
    commitWindow, requestKeyboard, invalidateInternalRequest, cancelNavigation,
    revealRow, setScrollTop, resetTravel, reset, bounds, schedule, dispose,
    get total() { return total; },
    get keyboardIndex() { return pending?.kind === "keyboard" ? pending.index : null; }});
}
