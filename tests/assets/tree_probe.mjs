import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";


class TestClassList {
  constructor() {
    this.values = new Set();
  }

  add(...values) {
    for (const value of values) {
      this.values.add(value);
    }
  }

  contains(value) {
    return this.values.has(value);
  }
}

class TestStyle {
  constructor() {
    this.values = new Map();
  }

  setProperty(name, value) {
    this.values.set(name, String(value));
  }

  getPropertyValue(name) {
    return this.values.get(name) ?? "";
  }

  set blockSize(value) {
    this.setProperty("block-size", value);
  }

  get blockSize() {
    return this.getPropertyValue("block-size");
  }
}

class TestElement {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.classList = new TestClassList();
    this.dataset = {};
    this.style = new TestStyle();
    this.attributes = new Map();
    this.value = "";
    this.listeners = new Map();
    this.parentElement = null;
    this.scrollTop = 0;
    this.clientHeight = 0;
    this.clampScrollOnReplace = false;
  }

  addEventListener(name, listener) {
    const listeners = this.listeners.get(name) ?? [];
    listeners.push(listener);
    this.listeners.set(name, listeners);
  }

  dispatch(name, event = {}) {
    if (event.target === undefined) {
      event.target = this;
    }
    event.currentTarget = this;
    for (const listener of this.listeners.get(name) ?? []) {
      listener(event);
    }
    if (!event.cancelBubble && this.parentElement !== null) {
      this.parentElement.dispatch(name, event);
    }
  }

  append(...children) {
    for (const child of children) {
      child.parentElement = this;
    }
    this.children.push(...children);
  }

  replaceChildren(...children) {
    for (const child of this.children) {
      if (child.parentElement === this) {
        child.parentElement = null;
      }
    }
    for (const child of children) {
      child.parentElement = this;
    }
    this.children = [...children];
    if (this.clampScrollOnReplace) {
      this.scrollTop = 0;
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  focus() {
    this.ownerDocument.activeElement = this;
    this.dispatch("focus");
  }

  get textContent() {
    return this.value;
  }

  set textContent(value) {
    assert.equal(typeof value, "string");
    this.value = value;
  }
}

class TestWindow {
  constructor() {
    this.animationFrames = [];
  }

  requestAnimationFrame(callback) {
    this.animationFrames.push(callback);
    return this.animationFrames.length;
  }

  flushAnimationFrame() {
    const callbacks = this.animationFrames;
    this.animationFrames = [];
    for (const callback of callbacks) {
      callback(0);
    }
  }
}

class TestDocument {
  constructor() {
    this.activeElement = null;
    this.created = 0;
    this.defaultView = new TestWindow();
  }

  createElement(tagName) {
    this.created += 1;
    return new TestElement(tagName, this);
  }
}

globalThis.Element = TestElement;

const treePath = process.argv[2];
const renderPath = process.argv[3];
assert.ok(treePath, "tree module path is required");
assert.ok(renderPath, "render module path is required");

const renderSource = await readFile(renderPath, "utf8");
const renderUrl = dataModuleUrl(renderSource);
const treeSource = await readFile(treePath, "utf8");
const renderSpecifier = '"./render.js"';
assert.equal(treeSource.split(renderSpecifier).length - 1, 1);
const linkedTreeSource = treeSource.replace(
  renderSpecifier,
  JSON.stringify(renderUrl),
);
const {ROW_H, createTree} = await import(dataModuleUrl(linkedTreeSource));

assert.equal(ROW_H, 28);
assert.throws(() => createTree({}), /tree root must be an Element/);
assert.throws(
  () => createTree(new TestDocument().createElement("div"), {toggle: true}),
  /tree toggle callback must be a function/,
);

const requested = [];
const toggled = [];
const activated = [];
const document = new TestDocument();
const root = document.createElement("div");
root.ariaLabel = "Plan";
let requestedGeneration = null;
let tree;
tree = createTree(root, {
  requestIndex: (index, generation) => {
    requested.push(index);
    requestedGeneration = generation;
  },
  toggle: (...value) => toggled.push(value),
  activate: (nodeId) => activated.push(nodeId),
});
assert.equal(root.getAttribute("role"), "tree");
assert.equal(root.role, undefined);
assert.equal(root.tabIndex, 0);
assert.ok(root.classList.contains("nami-tree"));
assert.equal(root.children.length, 2);
const topSpacer = root.children[0];
const bottomSpacer = root.children[1];
assertSpacer(topSpacer);
assertSpacer(bottomSpacer);

const firstGeneration = tree.beginWindowRequest();
const secondGeneration = tree.beginWindowRequest();
assert.equal(firstGeneration, 1);
assert.equal(secondGeneration, 2);

let staleReads = 0;
const unreadableWindow = new Proxy({}, {
  get() {
    staleReads += 1;
    throw new Error("stale window was read");
  },
  ownKeys() {
    staleReads += 1;
    throw new Error("stale window was enumerated");
  },
});
assert.equal(tree.commitWindow(firstGeneration, unreadableWindow), false);
assert.equal(staleReads, 0);

const hostileDisplay =
  "wave \u{1f30a} e\u0301 <img onerror=alert(1)> & \u6d77";
const longDisplay = `${"\u6ce2".repeat(600)} end`;
const accessedFields = new Map();
const trackedContainer = new Proxy(
  row(5, "node-container", hostileDisplay, {
    container: true,
    expanded: false,
    depth: 1,
    parent: 0,
    position: 1,
    setSize: 1,
  }),
  {
    get(target, property, receiver) {
      if (typeof property === "string") {
        accessedFields.set(property, (accessedFields.get(property) ?? 0) + 1);
      }
      return Reflect.get(target, property, receiver);
    },
  },
);
const firstWindow = Object.freeze({
  offset: 5,
  total: 10,
  rows: Object.freeze([
    trackedContainer,
    row(6, "node-leaf", longDisplay, {
      depth: 2,
      parent: 5,
    }),
    row(7, "projected-empty", "Projected empty", {
      container: true,
      expanded: null,
      depth: 1,
      parent: 0,
    }),
  ]),
});
assert.equal(tree.commitWindow(secondGeneration, firstWindow), true);
assert.deepEqual(
  [...accessedFields.keys()].sort(),
  [
    "depth", "display", "expanded", "first_child_visible_index", "node_id",
    "parent_visible_index",
    "position_in_set", "set_size", "visible_index",
  ],
);
assert.equal(root.children.length, 5);
assert.equal(topSpacer.style.blockSize, `${5 * ROW_H}px`);
assert.equal(bottomSpacer.style.blockSize, `${2 * ROW_H}px`);

const firstRows = treeItems(root);
assert.equal(firstRows.length, 3);
assert.equal(firstRows[0].dataset.nodeId, "node-container");
assert.equal(firstRows[0].id, "nami-tree-1-row-5");
assert.equal(firstRows[0].ariaLevel, "2");
assert.equal(firstRows[0].ariaPosInSet, "1");
assert.equal(firstRows[0].ariaSetSize, "1");
assert.equal(firstRows[0].ariaExpanded, "false");
assert.equal(firstRows[0].dataset.active, "true");
assert.equal(root.getAttribute("aria-activedescendant"), firstRows[0].id);
assert.equal(root.ariaActiveDescendant, undefined);
assert.equal(firstRows[0].children[1].textContent, hostileDisplay);
assert.equal(firstRows[1].ariaExpanded, undefined);
assert.equal(firstRows[1].children[1].textContent, longDisplay);
assert.equal(firstRows[2].ariaExpanded, undefined);
assert.ok(
  firstRows[2].children[0].classList.contains(
    "nami-tree-row__disclosure--leaf",
  ),
);

// Disclosure owns its pointer event. A synchronous replacement from toggle
// must not bubble into the detached row and activate it a second time.
const pointerDocument = new TestDocument();
const pointerRoot = pointerDocument.createElement("div");
const pointerToggles = [];
const pointerActivations = [];
let pointerTree;
pointerTree = createTree(pointerRoot, {
  toggle: (...value) => {
    pointerToggles.push(value);
    const generation = pointerTree.beginWindowRequest();
    pointerTree.commitWindow(generation, {
      offset: 0,
      total: 2,
      rows: [
        row(0, "pointer-container", "Pointer container", {
          container: true,
          expanded: true,
          firstChild: 1,
        }),
        row(1, "pointer-leaf", "Pointer leaf", {depth: 1, parent: 0}),
      ],
    });
  },
  activate: (nodeId) => pointerActivations.push(nodeId),
});
const pointerGeneration = pointerTree.beginWindowRequest();
assert.equal(pointerTree.commitWindow(pointerGeneration, {
  offset: 0,
  total: 1,
  rows: [
    row(0, "pointer-container", "Pointer container", {
      container: true,
      expanded: false,
    }),
  ],
}), true);
const pointerRows = treeItems(pointerRoot);
dispatchClick(pointerRows[0].children[0]);
assert.deepEqual(pointerToggles, [["pointer-container", true]]);
assert.deepEqual(pointerActivations, []);
assert.equal(pointerDocument.activeElement, pointerRoot);
assert.equal(
  pointerRoot.getAttribute("aria-activedescendant"),
  "nami-tree-2-row-0",
);
dispatchClick(treeItems(pointerRoot)[0].children[1]);
assert.deepEqual(pointerToggles, [["pointer-container", true]]);
assert.deepEqual(pointerActivations, ["pointer-container"]);
dispatchClick(treeItems(pointerRoot)[1].children[0]);
assert.deepEqual(pointerToggles, [["pointer-container", true]]);
assert.deepEqual(pointerActivations, ["pointer-container"]);
dispatchClick(treeItems(pointerRoot)[1]);
assert.deepEqual(pointerActivations, ["pointer-container", "pointer-leaf"]);
assert.equal(
  pointerRoot.getAttribute("aria-activedescendant"),
  "nami-tree-2-row-1",
);

const thrown = new Error("toggle sentinel");
const throwingRoot = new TestDocument().createElement("div");
const throwingActivations = [];
const throwingTree = createTree(throwingRoot, {
  toggle: () => {
    throw thrown;
  },
  activate: (nodeId) => throwingActivations.push(nodeId),
});
const throwingGeneration = throwingTree.beginWindowRequest();
throwingTree.commitWindow(throwingGeneration, {
  offset: 0,
  total: 1,
  rows: [row(0, "throwing-container", "Throwing container", {
    container: true,
  })],
});
const throwingEvent = clickEvent();
assert.throws(
  () => treeItems(throwingRoot)[0].children[0].dispatch(
    "click",
    throwingEvent,
  ),
  (error) => error === thrown,
);
assert.equal(throwingEvent.cancelBubble, true);
assert.deepEqual(throwingActivations, []);

dispatchKey(root, "ArrowRight");
assert.deepEqual(toggled, [["node-container", true]]);
dispatchKey(root, "Enter");
assert.deepEqual(activated, ["node-container"]);
dispatchKey(root, "ArrowDown");
dispatchKey(root, "ArrowDown");
assert.equal(root.getAttribute("aria-activedescendant"), firstRows[2].id);
dispatchKey(root, "ArrowRight");
assert.deepEqual(toggled, [["node-container", true]]);
dispatchKey(root, "Home");
assert.deepEqual(requested, [0]);

const homeGeneration = requestedGeneration;
assert.equal(typeof homeGeneration, "number");
assert.equal(tree.commitWindow(homeGeneration, {
  offset: 0,
  total: 10,
  rows: [
    row(0, "root", "Root", {
      container: true,
      expanded: true,
      firstChild: 1,
    }),
    row(1, "child", "Child", {depth: 1, parent: 0}),
    row(2, "sibling", "Sibling"),
  ],
}), true);
assert.equal(root.getAttribute("aria-activedescendant"), "nami-tree-1-row-0");
dispatchKey(root, "ArrowRight");
assert.equal(root.getAttribute("aria-activedescendant"), "nami-tree-1-row-1");
dispatchKey(root, "ArrowLeft");
assert.equal(root.getAttribute("aria-activedescendant"), "nami-tree-1-row-0");
dispatchKey(root, "ArrowDown");
assert.equal(root.getAttribute("aria-activedescendant"), "nami-tree-1-row-1");
dispatchKey(root, "End");
assert.deepEqual(requested, [0, 9]);

// Active-descendant navigation scrolls only the tree viewport and only when
// the complete fixed-height row falls outside it.
const viewportRoot = new TestDocument().createElement("div");
viewportRoot.clientHeight = 2 * ROW_H;
const viewportTree = createTree(viewportRoot);
const viewportGeneration = viewportTree.beginWindowRequest();
viewportTree.commitWindow(viewportGeneration, {
  offset: 0,
  total: 4,
  rows: [
    row(0, "viewport-0", "Viewport 0"),
    row(1, "viewport-1", "Viewport 1"),
    row(2, "viewport-2", "Viewport 2"),
    row(3, "viewport-3", "Viewport 3"),
  ],
});
assert.equal(viewportRoot.scrollTop, 0);
dispatchKey(viewportRoot, "ArrowDown");
assert.equal(viewportRoot.scrollTop, 0);
viewportRoot.scrollTop = ROW_H;
dispatchKey(viewportRoot, "ArrowDown");
assert.equal(viewportRoot.scrollTop, ROW_H);
dispatchKey(viewportRoot, "ArrowDown");
assert.equal(viewportRoot.scrollTop, 2 * ROW_H);
dispatchKey(viewportRoot, "Home");
assert.equal(viewportRoot.scrollTop, 0);
assert.equal(
  viewportRoot.getAttribute("aria-activedescendant"),
  "nami-tree-4-row-0",
);

const pagedRoot = new TestDocument().createElement("div");
pagedRoot.clientHeight = 2 * ROW_H;
const pagedRequests = [];
let pagedGeneration = null;
let pagedTree;
pagedTree = createTree(pagedRoot, {
  requestIndex: (index, generation) => {
    pagedRequests.push(index);
    pagedGeneration = generation;
  },
});
const pagedInitial = pagedTree.beginWindowRequest();
pagedTree.commitWindow(pagedInitial, {
  offset: 0,
  total: 6,
  rows: [row(0, "paged-0", "Paged 0"), row(1, "paged-1", "Paged 1")],
});
dispatchKey(pagedRoot, "End");
assert.deepEqual(pagedRequests, [5]);
assert.equal(pagedRoot.scrollTop, 0);
assert.equal(pagedTree.commitWindow(pagedGeneration, {
  offset: 4,
  total: 6,
  rows: [row(4, "paged-4", "Paged 4"), row(5, "paged-5", "Paged 5")],
}), true);
assert.equal(
  pagedRoot.getAttribute("aria-activedescendant"),
  "nami-tree-5-row-5",
);
assert.equal(pagedRoot.scrollTop, 4 * ROW_H);
dispatchKey(pagedRoot, "Home");
assert.deepEqual(pagedRequests, [5, 0]);
assert.equal(pagedTree.commitWindow(pagedGeneration, {
  offset: 0,
  total: 6,
  rows: [row(0, "paged-0", "Paged 0"), row(1, "paged-1", "Paged 1")],
}), true);
assert.equal(pagedRoot.scrollTop, 0);

// Scroll paging is last-state-wins and owns its request generations. The
// viewport can temporarily contain only a spacer, but it must not retain an
// offscreen active descendant or snap back when refocused during that gap.
const scrollDocument = new TestDocument();
const scrollRoot = scrollDocument.createElement("div");
scrollRoot.clientHeight = 4 * ROW_H;
const scrollRequests = [];
let scrollTree;
scrollTree = createTree(scrollRoot, {
  requestIndex: (index, generation) => {
    scrollRequests.push({index, generation});
  },
});
const scrollInitial = scrollTree.beginWindowRequest();
assert.equal(scrollTree.commitWindow(scrollInitial, {
  offset: 0,
  total: 300,
  rows: rows(0, 4, "scroll"),
}), true);
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests, []);

scrollRoot.scrollTop = 4 * ROW_H;
scrollRoot.dispatch("scroll");
scrollRoot.scrollTop = 8 * ROW_H;
scrollRoot.dispatch("scroll");
assert.equal(scrollDocument.defaultView.animationFrames.length, 1);
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests, [{index: 11, generation: 2}]);
assert.equal(scrollRoot.getAttribute("aria-activedescendant"), null);
scrollRoot.focus();
assert.equal(scrollRoot.scrollTop, 8 * ROW_H);
assert.equal(scrollRoot.getAttribute("aria-activedescendant"), null);

scrollRoot.dispatch("scroll");
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests, [{index: 11, generation: 2}]);

scrollRoot.scrollTop = 12 * ROW_H;
scrollRoot.dispatch("scroll");
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests, [
  {index: 11, generation: 2},
  {index: 15, generation: 3},
]);
assert.equal(scrollTree.commitWindow(2, unreadableWindow), false);
assert.equal(staleReads, 0);

scrollRoot.scrollTop = 0;
scrollRoot.dispatch("scroll");
scrollDocument.defaultView.flushAnimationFrame();
assert.equal(
  scrollRoot.getAttribute("aria-activedescendant"),
  "nami-tree-6-row-0",
);
assert.deepEqual(scrollRequests, [
  {index: 11, generation: 2},
  {index: 15, generation: 3},
]);
assert.equal(scrollTree.commitWindow(3, unreadableWindow), false);
assert.equal(staleReads, 0);

scrollRoot.scrollTop = 4 * ROW_H;
scrollRoot.dispatch("scroll");
scrollDocument.defaultView.flushAnimationFrame();
const trailingRequest = scrollRequests.at(-1);
assert.deepEqual(trailingRequest, {index: 7, generation: 5});
assert.equal(scrollTree.commitWindow(trailingRequest.generation, {
  offset: 4,
  total: 300,
  rows: rows(4, 4, "scroll"),
}), true);
assert.equal(scrollRoot.scrollTop, 4 * ROW_H);
assert.deepEqual(
  treeItems(scrollRoot).map((element) => element.dataset.nodeId),
  ["scroll-4", "scroll-5", "scroll-6", "scroll-7"],
);
assert.equal(
  scrollRoot.getAttribute("aria-activedescendant"),
  "nami-tree-6-row-7",
);
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests.at(-1), trailingRequest);

scrollRoot.scrollTop = 0;
scrollRoot.dispatch("scroll");
scrollDocument.defaultView.flushAnimationFrame();
const leadingRequest = scrollRequests.at(-1);
assert.deepEqual(leadingRequest, {index: 0, generation: 6});
assert.equal(scrollTree.commitWindow(leadingRequest.generation, {
  offset: 0,
  total: 300,
  rows: rows(0, 4, "scroll"),
}), true);
scrollDocument.defaultView.flushAnimationFrame();

// An external projection request cannot be superseded from its stale DOM.
const externalGeneration = scrollTree.beginWindowRequest();
scrollRoot.scrollTop = 20 * ROW_H;
scrollRoot.dispatch("scroll");
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests.at(-1), leadingRequest);
assert.equal(scrollTree.commitWindow(externalGeneration, {
  offset: 20,
  total: 300,
  rows: rows(20, 4, "external"),
}), true);
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests.at(-1), leadingRequest);

// A scroll frame queued before a keyboard request is stale and cannot cancel
// it. A scroll observed after a keyboard request is newer user intent.
scrollRoot.scrollTop = 24 * ROW_H;
scrollRoot.dispatch("scroll");
dispatchKey(scrollRoot, "End");
const endRequest = scrollRequests.at(-1);
assert.deepEqual(endRequest, {index: 299, generation: 8});
scrollDocument.defaultView.flushAnimationFrame();
assert.equal(scrollTree.commitWindow(endRequest.generation, {
  offset: 296,
  total: 300,
  rows: rows(296, 4, "end"),
}), true);
assert.equal(scrollRoot.scrollTop, 296 * ROW_H);
scrollDocument.defaultView.flushAnimationFrame();

const resetGeneration = scrollTree.beginWindowRequest();
assert.equal(scrollTree.commitWindow(resetGeneration, {
  offset: 20,
  total: 300,
  rows: rows(20, 4, "newer"),
}), true);
scrollDocument.defaultView.flushAnimationFrame();
dispatchKey(scrollRoot, "End");
const supersededKeyboard = scrollRequests.at(-1);
scrollRoot.scrollTop = 21 * ROW_H;
scrollRoot.dispatch("scroll");
scrollDocument.defaultView.flushAnimationFrame();
const newerScroll = scrollRequests.at(-1);
assert.equal(newerScroll.index, 24);
assert.ok(newerScroll.generation > supersededKeyboard.generation);
assert.equal(
  scrollTree.commitWindow(supersededKeyboard.generation, unreadableWindow),
  false,
);
assert.equal(staleReads, 0);
assert.equal(scrollTree.commitWindow(newerScroll.generation, {
  offset: 21,
  total: 300,
  rows: rows(21, 4, "newer-scroll"),
}), true);
assert.equal(scrollRoot.scrollTop, 21 * ROW_H);
assert.equal(
  scrollRoot.getAttribute("aria-activedescendant"),
  "nami-tree-6-row-24",
);

// A wheel movement wholly inside the current window updates only the
// presentation focus; it neither requests a page nor activates a node.
const coveredDocument = new TestDocument();
const coveredRoot = coveredDocument.createElement("div");
coveredRoot.clientHeight = 4 * ROW_H;
const coveredRequests = [];
const coveredActivations = [];
const coveredTree = createTree(coveredRoot, {
  requestIndex: (...value) => coveredRequests.push(value),
  activate: (...value) => coveredActivations.push(value),
});
const coveredGeneration = coveredTree.beginWindowRequest();
coveredTree.commitWindow(coveredGeneration, {
  offset: 0,
  total: 8,
  rows: rows(0, 8, "covered"),
});
coveredDocument.defaultView.flushAnimationFrame();
coveredRoot.scrollTop = 4 * ROW_H;
coveredRoot.dispatch("scroll");
coveredDocument.defaultView.flushAnimationFrame();
assert.deepEqual(coveredRequests, []);
assert.deepEqual(coveredActivations, []);
assert.equal(coveredRoot.scrollTop, 4 * ROW_H);
assert.equal(
  coveredRoot.getAttribute("aria-activedescendant"),
  "nami-tree-7-row-4",
);

// Exact and fractional viewport boundaries select only an intersected spacer.
const boundaryDocument = new TestDocument();
const boundaryRoot = boundaryDocument.createElement("div");
boundaryRoot.clientHeight = 4 * ROW_H;
const boundaryRequests = [];
const boundaryTree = createTree(boundaryRoot, {
  requestIndex: (index, generation) => {
    boundaryRequests.push({index, generation});
  },
});
const boundaryInitial = boundaryTree.beginWindowRequest();
boundaryTree.commitWindow(boundaryInitial, {
  offset: 0,
  total: 300,
  rows: rows(0, 4, "boundary"),
});
boundaryDocument.defaultView.flushAnimationFrame();
boundaryRoot.dispatch("scroll");
boundaryDocument.defaultView.flushAnimationFrame();
assert.deepEqual(boundaryRequests, []);
boundaryRoot.scrollTop = 0.25;
boundaryRoot.dispatch("scroll");
boundaryDocument.defaultView.flushAnimationFrame();
assert.deepEqual(boundaryRequests, [{index: 4, generation: 2}]);
boundaryRoot.scrollTop = 0;
boundaryRoot.dispatch("scroll");
boundaryDocument.defaultView.flushAnimationFrame();
assert.equal(boundaryTree.commitWindow(2, unreadableWindow), false);
const boundaryReset = boundaryTree.beginWindowRequest();
boundaryRoot.scrollTop = 4 * ROW_H;
boundaryTree.commitWindow(boundaryReset, {
  offset: 4,
  total: 300,
  rows: rows(4, 4, "boundary"),
});
boundaryDocument.defaultView.flushAnimationFrame();
boundaryRoot.dispatch("scroll");
boundaryDocument.defaultView.flushAnimationFrame();
assert.equal(boundaryRequests.length, 1);
boundaryRoot.scrollTop = (4 * ROW_H) - 0.25;
boundaryRoot.dispatch("scroll");
boundaryDocument.defaultView.flushAnimationFrame();
assert.deepEqual(boundaryRequests.at(-1), {index: 3, generation: 5});

// A throwing request callback leaves the old DOM and scroll position intact,
// keeps prior generations stale, and permits a later scroll retry.
const callbackError = new Error("request sentinel");
const throwingRequestDocument = new TestDocument();
const throwingRequestRoot = throwingRequestDocument.createElement("div");
throwingRequestRoot.clientHeight = 4 * ROW_H;
const throwingRequests = [];
let throwRequest = true;
const throwingRequestTree = createTree(throwingRequestRoot, {
  requestIndex: (index, generation) => {
    throwingRequests.push({index, generation});
    if (throwRequest) {
      throwRequest = false;
      throw callbackError;
    }
  },
});
const throwingRequestInitial = throwingRequestTree.beginWindowRequest();
throwingRequestTree.commitWindow(throwingRequestInitial, {
  offset: 0,
  total: 300,
  rows: rows(0, 4, "throw-request"),
});
throwingRequestDocument.defaultView.flushAnimationFrame();
throwingRequestRoot.scrollTop = 4 * ROW_H;
throwingRequestRoot.dispatch("scroll");
const throwingFingerprint = fingerprint(throwingRequestRoot);
assert.throws(
  () => throwingRequestDocument.defaultView.flushAnimationFrame(),
  (error) => error === callbackError,
);
assert.equal(throwingRequestRoot.scrollTop, 4 * ROW_H);
assert.deepEqual(fingerprint(throwingRequestRoot), throwingFingerprint);
assert.equal(
  throwingRequestTree.commitWindow(throwingRequestInitial, unreadableWindow),
  false,
);
throwingRequestRoot.dispatch("scroll");
throwingRequestDocument.defaultView.flushAnimationFrame();
assert.deepEqual(throwingRequests, [
  {index: 7, generation: 2},
  {index: 7, generation: 3},
]);

// A malformed current response is read completely before mounted geometry or
// active state changes, and the same generation remains retryable.
const atomicDocument = new TestDocument();
const atomicRoot = atomicDocument.createElement("div");
atomicRoot.clientHeight = 2 * ROW_H;
const atomicTree = createTree(atomicRoot);
const atomicInitial = atomicTree.beginWindowRequest();
atomicTree.commitWindow(atomicInitial, {
  offset: 0,
  total: 3,
  rows: rows(0, 2, "atomic"),
});
atomicDocument.defaultView.flushAnimationFrame();
atomicRoot.scrollTop = ROW_H;
const atomicGeneration = atomicTree.beginWindowRequest();
const atomicFingerprint = fingerprint(atomicRoot);
const atomicActiveDescendant = atomicRoot.getAttribute("aria-activedescendant");
const atomicActiveFlags = treeItems(atomicRoot).map(
  (element) => element.dataset.active ?? null,
);
const malformedRow = new Proxy(row(1, "malformed", "Malformed"), {
  get(target, property, receiver) {
    if (property === "set_size") {
      throw callbackError;
    }
    return Reflect.get(target, property, receiver);
  },
});
assert.throws(
  () => atomicTree.commitWindow(atomicGeneration, {
    offset: 1,
    total: 3,
    rows: [malformedRow],
  }),
  (error) => error === callbackError,
);
assert.equal(atomicRoot.scrollTop, ROW_H);
assert.deepEqual(fingerprint(atomicRoot), atomicFingerprint);
assert.equal(
  atomicRoot.getAttribute("aria-activedescendant"),
  atomicActiveDescendant,
);
assert.deepEqual(
  treeItems(atomicRoot).map((element) => element.dataset.active ?? null),
  atomicActiveFlags,
);
assert.equal(atomicTree.commitWindow(atomicGeneration, {
  offset: 1,
  total: 3,
  rows: rows(1, 2, "atomic-retry"),
}), true);

// Enter is newer than an in-flight passive page and invalidates that response.
const intentDocument = new TestDocument();
const intentRoot = intentDocument.createElement("div");
intentRoot.clientHeight = 4 * ROW_H;
const intentRequests = [];
const intentActivations = [];
const intentTree = createTree(intentRoot, {
  requestIndex: (index, generation) => {
    intentRequests.push({index, generation});
  },
  activate: (nodeId) => intentActivations.push(nodeId),
});
const intentInitial = intentTree.beginWindowRequest();
intentTree.commitWindow(intentInitial, {
  offset: 0,
  total: 300,
  rows: rows(0, 4, "intent"),
});
intentDocument.defaultView.flushAnimationFrame();
intentRoot.scrollTop = ROW_H;
intentRoot.dispatch("scroll");
intentDocument.defaultView.flushAnimationFrame();
const passiveIntentRequest = intentRequests.at(-1);
assert.equal(passiveIntentRequest.index, 4);
dispatchKey(intentRoot, "Enter");
assert.deepEqual(intentActivations, ["intent-1"]);
assert.equal(
  intentTree.commitWindow(passiveIntentRequest.generation, unreadableWindow),
  false,
);

// A delayed event from a rendered-key programmatic reveal cannot masquerade
// as a newer user scroll and cancel a subsequent off-window key request.
const programDocument = new TestDocument();
const programRoot = programDocument.createElement("div");
programRoot.clientHeight = 4 * ROW_H;
const programRequests = [];
const programTree = createTree(programRoot, {
  requestIndex: (index, generation) => {
    programRequests.push({index, generation});
  },
});
const programInitial = programTree.beginWindowRequest();
programTree.commitWindow(programInitial, {
  offset: 0,
  total: 300,
  rows: rows(0, 8, "program"),
});
programDocument.defaultView.flushAnimationFrame();
for (let index = 0; index < 4; index += 1) {
  dispatchKey(programRoot, "ArrowDown");
}
assert.equal(programRoot.scrollTop, ROW_H);
dispatchKey(programRoot, "End");
const programKeyboard = programRequests.at(-1);
programRoot.dispatch("scroll");
programDocument.defaultView.flushAnimationFrame();
assert.deepEqual(programRequests, [programKeyboard]);
assert.equal(programTree.commitWindow(programKeyboard.generation, {
  offset: 296,
  total: 300,
  rows: rows(296, 4, "program-end"),
}), true);

const shortDocument = new TestDocument();
const shortRoot = shortDocument.createElement("div");
shortRoot.clientHeight = ROW_H - 1;
const shortTree = createTree(shortRoot);
const shortGeneration = shortTree.beginWindowRequest();
shortTree.commitWindow(shortGeneration, {
  offset: 0,
  total: 1,
  rows: rows(0, 1, "short"),
});
shortDocument.defaultView.flushAnimationFrame();
assert.equal(shortRoot.getAttribute("aria-activedescendant"), null);

// A valid narrow response is terminal for the viewport snapshot that asked
// for it. It cannot alternate missing endpoints without a newer scroll.
const narrowDocument = new TestDocument();
const narrowRoot = narrowDocument.createElement("div");
narrowRoot.clientHeight = 4 * ROW_H;
narrowRoot.clampScrollOnReplace = true;
const narrowRequests = [];
const narrowTree = createTree(narrowRoot, {
  requestIndex: (index, generation) => {
    narrowRequests.push({index, generation});
  },
});
const narrowInitial = narrowTree.beginWindowRequest();
narrowTree.commitWindow(narrowInitial, {
  offset: 0,
  total: 20,
  rows: rows(0, 4, "narrow"),
});
narrowDocument.defaultView.flushAnimationFrame();
narrowRoot.scrollTop = 4 * ROW_H;
narrowRoot.dispatch("scroll");
narrowDocument.defaultView.flushAnimationFrame();
assert.deepEqual(narrowRequests, [{index: 7, generation: 2}]);
narrowRoot.dispatch("scroll");
assert.equal(narrowDocument.defaultView.animationFrames.length, 1);
assert.equal(narrowTree.commitWindow(2, {
  offset: 7,
  total: 20,
  rows: rows(7, 1, "narrow-response"),
}), true);
assert.equal(narrowRoot.scrollTop, 4 * ROW_H);
narrowDocument.defaultView.flushAnimationFrame();
assert.equal(narrowDocument.defaultView.animationFrames.length, 0);
narrowRoot.dispatch("scroll");
assert.equal(narrowDocument.defaultView.animationFrames.length, 0);
assert.deepEqual(narrowRequests, [{index: 7, generation: 2}]);

// A changed viewport observed while that narrow response is in flight still
// receives one new last-state-wins request and can converge normally.
const changedDocument = new TestDocument();
const changedRoot = changedDocument.createElement("div");
changedRoot.clientHeight = 4 * ROW_H;
const changedRequests = [];
const changedTree = createTree(changedRoot, {
  requestIndex: (index, generation) => {
    changedRequests.push({index, generation});
  },
});
const changedInitial = changedTree.beginWindowRequest();
changedTree.commitWindow(changedInitial, {
  offset: 0,
  total: 20,
  rows: rows(0, 4, "changed"),
});
changedDocument.defaultView.flushAnimationFrame();
changedRoot.scrollTop = 4 * ROW_H;
changedRoot.dispatch("scroll");
changedDocument.defaultView.flushAnimationFrame();
assert.deepEqual(changedRequests, [{index: 7, generation: 2}]);
changedRoot.scrollTop = 8 * ROW_H;
changedRoot.dispatch("scroll");
assert.equal(changedTree.commitWindow(2, {
  offset: 7,
  total: 20,
  rows: rows(7, 1, "changed-narrow"),
}), true);
changedDocument.defaultView.flushAnimationFrame();
assert.deepEqual(changedRequests, [
  {index: 7, generation: 2},
  {index: 11, generation: 3},
]);
assert.equal(changedTree.commitWindow(3, {
  offset: 8,
  total: 20,
  rows: rows(8, 4, "changed-final"),
}), true);
assert.equal(changedDocument.defaultView.animationFrames.length, 0);
assert.equal(changedRoot.scrollTop, 8 * ROW_H);

const unmeasuredRoot = new TestDocument().createElement("div");
unmeasuredRoot.scrollTop = 17;
const unmeasuredTree = createTree(unmeasuredRoot);
const unmeasuredGeneration = unmeasuredTree.beginWindowRequest();
unmeasuredTree.commitWindow(unmeasuredGeneration, {
  offset: 5,
  total: 6,
  rows: [row(5, "unmeasured", "Unmeasured")],
});
assert.equal(unmeasuredRoot.scrollTop, 17);
unmeasuredRoot.clientHeight = ROW_H;
unmeasuredRoot.focus();
assert.equal(unmeasuredRoot.scrollTop, 5 * ROW_H);

// Arbitrary recycling cannot leave a stale active index or descendant.
const recycledGeneration = tree.beginWindowRequest();
assert.equal(tree.commitWindow(recycledGeneration, {
  offset: 7,
  total: 10,
  rows: [row(7, "seven", "Seven"), row(8, "eight", "Eight")],
}, "missing-preferred"), true);
assert.equal(root.getAttribute("aria-activedescendant"), "nami-tree-1-row-7");
dispatchKey(root, "ArrowRight");
assert.equal(root.getAttribute("aria-activedescendant"), "nami-tree-1-row-7");

const emptyGeneration = tree.beginWindowRequest();
assert.equal(tree.commitWindow(emptyGeneration, {
  offset: 10,
  total: 10,
  rows: [],
}), true);
assert.equal(root.getAttribute("aria-activedescendant"), null);
assert.equal(treeItems(root).length, 0);
root.focus();
assert.equal(root.getAttribute("aria-activedescendant"), null);
dispatchKey(root, "Home");
assert.deepEqual(requested, [0, 9, 0]);
const repopulatedGeneration = requestedGeneration;
assert.equal(tree.commitWindow(repopulatedGeneration, {
  offset: 0,
  total: 10,
  rows: [row(0, "new-root", "New root")],
}), true);
assert.equal(root.getAttribute("aria-activedescendant"), "nami-tree-1-row-0");

const maximumGeneration = tree.beginWindowRequest();
const maximumRows = Array.from({length: 256}, (_, index) =>
  row(index, `node-${index}`, index === 255 ? longDisplay : `Row ${index}`, {
    container: index === 0,
    expanded: index === 0,
    firstChild: index === 0 ? 1 : null,
    depth: index === 0 ? 0 : 1,
    parent: index === 0 ? null : 0,
    position: index === 0 ? 1 : index,
    setSize: index === 0 ? 1 : 255,
  }));
assert.equal(tree.commitWindow(maximumGeneration, {
  offset: 0,
  total: 256,
  rows: maximumRows,
}), true);
assert.equal(treeItems(root).length, 256);
assert.equal(root.children.length, 258);
assert.equal(treeItems(root).at(-1).children[1].textContent, longDisplay);

const staleGeneration = tree.beginWindowRequest();
const committedFingerprint = fingerprint(root);
assert.equal(tree.commitWindow(maximumGeneration, unreadableWindow), false);
assert.equal(staleReads, 0);
assert.deepEqual(fingerprint(root), committedFingerprint);
assert.equal(staleGeneration, maximumGeneration + 1);

function row(index, nodeId, display, options = {}) {
  const container = options.container ?? false;
  return Object.freeze({
    node_id: nodeId,
    display,
    depth: options.depth ?? 0,
    is_container: container,
    visible_index: index,
    parent_visible_index: options.parent ?? null,
    first_child_visible_index: options.firstChild ?? null,
    position_in_set: options.position ?? 1,
    set_size: options.setSize ?? 1,
    expanded: container
      ? (options.expanded === undefined ? false : options.expanded)
      : null,
  });
}

function rows(offset, count, prefix) {
  return Array.from({length: count}, (_, relativeIndex) => {
    const index = offset + relativeIndex;
    return row(index, `${prefix}-${index}`, `${prefix} ${index}`);
  });
}

function dispatchKey(element, key) {
  let prevented = false;
  element.dispatch("keydown", {
    key,
    defaultPrevented: false,
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    preventDefault() {
      prevented = true;
    },
  });
  assert.equal(prevented, true);
}

function clickEvent() {
  return {
    cancelBubble: false,
    stopPropagation() {
      this.cancelBubble = true;
    },
  };
}

function dispatchClick(element) {
  element.dispatch("click", clickEvent());
}

function assertSpacer(element) {
  assert.ok(element.classList.contains("nami-tree__spacer"));
  assert.equal(element.ariaHidden, "true");
  assert.notEqual(element.getAttribute("role"), "treeitem");
}

function treeItems(element) {
  const items = element.children.filter(
    (child) => child.getAttribute("role") === "treeitem",
  );
  for (const item of items) {
    assert.equal(item.role, undefined);
  }
  return items;
}

function fingerprint(element) {
  return element.children.map((child) => ({
    id: child.id ?? null,
    nodeId: child.dataset.nodeId ?? null,
    text: child.children.at(-1)?.textContent ?? null,
    blockSize: child.style.blockSize,
  }));
}

function dataModuleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}
