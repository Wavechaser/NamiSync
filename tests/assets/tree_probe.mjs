import assert from "node:assert/strict";
import {createHash} from "node:crypto";
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
const fixturePath = process.argv[4];
const expectedFixtureSha256 = process.argv[5];
assert.ok(treePath, "tree module path is required");
assert.ok(renderPath, "render module path is required");
assert.ok(fixturePath, "tree fixture path is required");
assert.match(
  expectedFixtureSha256 ?? "",
  /^[0-9a-f]{64}$/u,
  "tree fixture SHA-256 is required",
);

const fixtureBytes = await readFile(fixturePath);
const fixtureSha256 = createHash("sha256").update(fixtureBytes).digest("hex");
assert.equal(fixtureSha256, expectedFixtureSha256);
const fixtureText = new TextDecoder("utf-8", {fatal: true}).decode(fixtureBytes);
const fixture = JSON.parse(fixtureText);
assertTreeFixture(fixture);
const fixtureViews = fixture.views;
const fixtureNodeIds = fixture.node_ids;

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

const layoutCodePoints = [
  ...Array.from({length: 0x20}, (_, index) => index),
  ...Array.from({length: 0x21}, (_, index) => 0x7f + index),
  0x00ad,
  0x061c,
  0x200b,
  0x200e,
  0x200f,
  ...Array.from({length: 0x07}, (_, index) => 0x2028 + index),
  ...Array.from({length: 0x10}, (_, index) => 0x2060 + index),
  0xfeff,
  0x27e6,
  0x27e7,
];
const layoutDisplay =
  `layout-${layoutCodePoints.map((codePoint) =>
    String.fromCodePoint(codePoint)).join("")}-end`;
const layoutRendered = `layout-${layoutCodePoints.map(
  (codePoint) => `⟦U+${codePoint.toString(16).toUpperCase().padStart(4, "0")}⟧`,
).join("")}-end`;
const activeLayoutControlPattern =
  /[\u0000-\u001f\u007f-\u009f\u00ad\u061c\u200b\u200e-\u200f\u2028-\u202e\u2060-\u206f\ufeff]/u;
const supplementalDisplay =
  "wave \u{1f30a}\ufe0f e\u0301 <img onerror=alert(1)> العربية עברית A\u200cB\u200dC \u{e0020} & \u6d77";
const supplementalLongDisplay = `${"\u6ce2".repeat(600)} end`;

const layoutFixtureRow = fixtureViews.layout_control.rows[1];
assert.equal(layoutFixtureRow.node_id, fixtureNodeIds.layout_control);
const layoutFixtureRendered = visibleFilesystemText(layoutFixtureRow.display);
const accessedFields = new Map();
const trackedContainer = new Proxy(
  fixtureViews.head.rows[1],
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
  ...fixtureViews.head,
  rows: Object.freeze([
    fixtureViews.head.rows[0],
    trackedContainer,
    ...fixtureViews.head.rows.slice(2),
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
assert.equal(root.children.length, 6);
assert.equal(topSpacer.style.blockSize, "0px");
assert.equal(
  bottomSpacer.style.blockSize,
  `${(fixtureViews.head.total - fixtureViews.head.rows.length) * ROW_H}px`,
);

let firstRows = treeItems(root);
assert.equal(firstRows.length, 4);
assert.equal(firstRows[0].dataset.nodeId, fixtureViews.head.rows[0].node_id);
assert.equal(firstRows[0].id, "nami-tree-1-row-0");
assert.equal(firstRows[0].ariaLevel, "1");
assert.equal(firstRows[0].ariaPosInSet, "1");
assert.equal(firstRows[0].ariaSetSize, "1");
assert.equal(firstRows[0].ariaExpanded, "true");
assert.equal(firstRows[0].dataset.active, "true");
assert.equal(root.getAttribute("aria-activedescendant"), firstRows[0].id);
assert.equal(root.ariaActiveDescendant, undefined);
for (const [index, element] of firstRows.entries()) {
  const sourceRow = fixtureViews.head.rows[index];
  assert.equal(element.ariaLevel, String(sourceRow.depth + 1));
  assert.equal(element.ariaPosInSet, String(sourceRow.position_in_set));
  assert.equal(element.ariaSetSize, String(sourceRow.set_size));
}
assert.equal(firstRows[1].dataset.nodeId, fixtureNodeIds.projection);
assert.equal(firstRows[1].ariaExpanded, "true");
assert.equal(firstRows[2].ariaExpanded, undefined);
assert.equal(firstRows[3].dataset.nodeId, fixtureNodeIds.layout_control);
assert.equal(firstRows[3].children[1].textContent, layoutFixtureRendered);
assert.equal(
  activeLayoutControlPattern.test(firstRows[3].children[1].textContent),
  false,
);
assert.ok(
  firstRows[3].children[0].classList.contains(
    "nami-tree-row__disclosure--leaf",
  ),
);

const nextGeneration = tree.beginWindowRequest();
assert.equal(tree.commitWindow(nextGeneration, fixtureViews.next), true);
const nextRows = treeItems(root);
assert.equal(nextRows[0].dataset.nodeId, fixtureNodeIds.ordinary_unicode);
assert.equal(
  nextRows[0].children[1].textContent,
  fixtureViews.next.rows[0].display,
);
assert.equal(nextRows[1].dataset.nodeId, fixtureNodeIds.long_unicode);
assert.equal(
  nextRows[1].children[1].textContent,
  fixtureViews.next.rows[1].display,
);
const restoredHeadGeneration = tree.beginWindowRequest();
assert.equal(
  tree.commitWindow(
    restoredHeadGeneration,
    fixtureViews.head,
    fixtureViews.head.rows[0].node_id,
  ),
  true,
);
firstRows = treeItems(root);

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
    pointerTree.commitWindow(generation, fixtureViews.pointer_expanded);
  },
  activate: (nodeId) => pointerActivations.push(nodeId),
});
const pointerGeneration = pointerTree.beginWindowRequest();
assert.equal(
  pointerTree.commitWindow(
    pointerGeneration,
    fixtureViews.pointer_collapsed,
  ),
  true,
);
const pointerRows = treeItems(pointerRoot);
const pointerContainer = pointerRows.find(
  (element) => element.dataset.nodeId === fixtureNodeIds.projection,
);
assert.ok(pointerContainer);
dispatchClick(pointerContainer.children[0]);
assert.deepEqual(pointerToggles, [[fixtureNodeIds.projection, true]]);
assert.deepEqual(pointerActivations, []);
assert.equal(pointerDocument.activeElement, pointerRoot);
assert.equal(
  pointerRoot.getAttribute("aria-activedescendant"),
  pointerContainer.id,
);
const expandedPointerRows = treeItems(pointerRoot);
const expandedContainer = expandedPointerRows.find(
  (element) => element.dataset.nodeId === fixtureNodeIds.projection,
);
const pointerLeaf = expandedPointerRows.find(
  (element) => element.dataset.nodeId === fixtureViews.pointer_expanded.rows[2].node_id,
);
assert.ok(expandedContainer);
assert.ok(pointerLeaf);
dispatchClick(expandedContainer.children[1]);
assert.deepEqual(pointerToggles, [[fixtureNodeIds.projection, true]]);
assert.deepEqual(pointerActivations, [fixtureNodeIds.projection]);
dispatchClick(pointerLeaf.children[0]);
assert.deepEqual(pointerToggles, [[fixtureNodeIds.projection, true]]);
assert.deepEqual(pointerActivations, [fixtureNodeIds.projection]);
dispatchClick(pointerLeaf);
assert.deepEqual(pointerActivations, [
  fixtureNodeIds.projection,
  pointerLeaf.dataset.nodeId,
]);
assert.equal(
  pointerRoot.getAttribute("aria-activedescendant"),
  pointerLeaf.id,
);

const triStateRoot = new TestDocument().createElement("div");
const triStateTree = createTree(triStateRoot);
const observedExpandedStates = [];
for (const name of [
  "pointer_expanded",
  "pointer_collapsed",
  "projected_empty",
]) {
  const generation = triStateTree.beginWindowRequest();
  assert.equal(triStateTree.commitWindow(generation, fixtureViews[name]), true);
  const projection = treeItems(triStateRoot).find(
    (element) => element.dataset.nodeId === fixtureNodeIds.projection,
  );
  assert.ok(projection);
  observedExpandedStates.push(projection.ariaExpanded ?? null);
}
assert.deepEqual(observedExpandedStates, ["true", "false", null]);

const keyTreeRoot = new TestDocument().createElement("div");
const keyToggles = [];
let keyTree;
keyTree = createTree(keyTreeRoot, {
  toggle: (nodeId, expanded) => {
    keyToggles.push([nodeId, expanded]);
    const generation = keyTree.beginWindowRequest();
    keyTree.commitWindow(
      generation,
      expanded
        ? fixtureViews.pointer_expanded
        : fixtureViews.pointer_collapsed,
    );
  },
});
const keyGeneration = keyTree.beginWindowRequest();
keyTree.commitWindow(keyGeneration, fixtureViews.pointer_collapsed);
dispatchKey(keyTreeRoot, "ArrowDown");
dispatchKey(keyTreeRoot, "ArrowRight");
assert.deepEqual(keyToggles, [[fixtureNodeIds.projection, true]]);
dispatchKey(keyTreeRoot, "ArrowRight");
assert.equal(
  keyTreeRoot.getAttribute("aria-activedescendant"),
  treeItems(keyTreeRoot)[2].id,
);
dispatchKey(keyTreeRoot, "ArrowLeft");
assert.equal(
  keyTreeRoot.getAttribute("aria-activedescendant"),
  treeItems(keyTreeRoot)[1].id,
);
dispatchKey(keyTreeRoot, "ArrowLeft");
assert.deepEqual(keyToggles, [
  [fixtureNodeIds.projection, true],
  [fixtureNodeIds.projection, false],
]);

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
  rows: [localRow(0, "throwing-container", "Throwing container", {
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
assert.equal(
  root.getAttribute("aria-activedescendant"),
  firstRows[1].id,
);
dispatchKey(root, "Enter");
assert.deepEqual(activated, [fixtureNodeIds.projection]);
dispatchKey(root, "ArrowDown");
dispatchKey(root, "ArrowDown");
assert.equal(root.getAttribute("aria-activedescendant"), firstRows[3].id);
dispatchKey(root, "Enter");
assert.deepEqual(activated, [
  fixtureNodeIds.projection,
  fixtureNodeIds.layout_control,
]);
assert.deepEqual(toggled, []);
dispatchKey(root, "End");
assert.deepEqual(requested, [fixtureViews.maximum.total - 1]);
assert.equal(
  tree.commitWindow(requestedGeneration, fixtureViews.tail),
  true,
);
assert.equal(
  topSpacer.style.blockSize,
  `${fixtureViews.tail.offset * ROW_H}px`,
);
assert.equal(bottomSpacer.style.blockSize, "0px");
assert.equal(
  root.getAttribute("aria-activedescendant"),
  treeItems(root).at(-1).id,
);
dispatchKey(root, "Home");
assert.deepEqual(requested, [fixtureViews.maximum.total - 1, 0]);
assert.equal(
  tree.commitWindow(requestedGeneration, fixtureViews.head),
  true,
);
assert.equal(
  root.getAttribute("aria-activedescendant"),
  treeItems(root)[0].id,
);

// Active-descendant navigation scrolls only the tree viewport and only when
// the complete fixed-height row falls outside it.
const viewportRoot = new TestDocument().createElement("div");
viewportRoot.clientHeight = 2 * ROW_H;
const viewportTree = createTree(viewportRoot);
const viewportGeneration = viewportTree.beginWindowRequest();
viewportTree.commitWindow(viewportGeneration, fixtureWindow(0, 4));
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
  treeItems(viewportRoot)[0].id,
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
pagedTree.commitWindow(pagedInitial, fixtureWindow(0, 2));
dispatchKey(pagedRoot, "End");
assert.deepEqual(pagedRequests, [fixtureViews.maximum.total - 1]);
assert.equal(pagedRoot.scrollTop, 0);
assert.equal(
  pagedTree.commitWindow(pagedGeneration, fixtureViews.tail),
  true,
);
assert.equal(
  pagedRoot.getAttribute("aria-activedescendant"),
  treeItems(pagedRoot).at(-1).id,
);
assert.equal(
  pagedRoot.scrollTop,
  (fixtureViews.tail.total * ROW_H) - pagedRoot.clientHeight,
);
dispatchKey(pagedRoot, "Home");
assert.deepEqual(pagedRequests, [fixtureViews.maximum.total - 1, 0]);
assert.equal(
  pagedTree.commitWindow(pagedGeneration, fixtureWindow(0, 2)),
  true,
);
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
assert.equal(
  scrollTree.commitWindow(scrollInitial, fixtureWindow(0, 4)),
  true,
);
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
  treeItems(scrollRoot)[0].id,
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
assert.equal(
  scrollTree.commitWindow(trailingRequest.generation, fixtureWindow(4, 4)),
  true,
);
assert.equal(scrollRoot.scrollTop, 4 * ROW_H);
assert.deepEqual(
  treeItems(scrollRoot).map((element) => element.dataset.nodeId),
  fixtureViews.maximum.rows.slice(4, 8).map((rowValue) => rowValue.node_id),
);
assert.equal(
  scrollRoot.getAttribute("aria-activedescendant"),
  treeItems(scrollRoot).at(-1).id,
);
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests.at(-1), trailingRequest);

scrollRoot.scrollTop = 0;
scrollRoot.dispatch("scroll");
scrollDocument.defaultView.flushAnimationFrame();
const leadingRequest = scrollRequests.at(-1);
assert.deepEqual(leadingRequest, {index: 0, generation: 6});
assert.equal(
  scrollTree.commitWindow(leadingRequest.generation, fixtureWindow(0, 4)),
  true,
);
scrollDocument.defaultView.flushAnimationFrame();

// An external projection request cannot be superseded from its stale DOM.
const externalGeneration = scrollTree.beginWindowRequest();
scrollRoot.scrollTop = 20 * ROW_H;
scrollRoot.dispatch("scroll");
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests.at(-1), leadingRequest);
assert.equal(
  scrollTree.commitWindow(externalGeneration, fixtureWindow(20, 4)),
  true,
);
scrollDocument.defaultView.flushAnimationFrame();
assert.deepEqual(scrollRequests.at(-1), leadingRequest);

// A scroll frame queued before a keyboard request is stale and cannot cancel
// it. A scroll observed after a keyboard request is newer user intent.
scrollRoot.scrollTop = 24 * ROW_H;
scrollRoot.dispatch("scroll");
dispatchKey(scrollRoot, "End");
const endRequest = scrollRequests.at(-1);
assert.deepEqual(endRequest, {
  index: fixtureViews.maximum.total - 1,
  generation: 8,
});
scrollDocument.defaultView.flushAnimationFrame();
assert.equal(
  scrollTree.commitWindow(endRequest.generation, fixtureViews.tail),
  true,
);
assert.equal(scrollRoot.scrollTop, fixtureViews.tail.offset * ROW_H);
scrollDocument.defaultView.flushAnimationFrame();

const resetGeneration = scrollTree.beginWindowRequest();
assert.equal(
  scrollTree.commitWindow(resetGeneration, fixtureWindow(20, 4)),
  true,
);
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
assert.equal(
  scrollTree.commitWindow(newerScroll.generation, fixtureWindow(21, 4)),
  true,
);
assert.equal(scrollRoot.scrollTop, 21 * ROW_H);
assert.equal(
  scrollRoot.getAttribute("aria-activedescendant"),
  treeItems(scrollRoot).at(-1).id,
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
coveredTree.commitWindow(coveredGeneration, fixtureWindow(0, 8));
coveredDocument.defaultView.flushAnimationFrame();
coveredRoot.scrollTop = 4 * ROW_H;
coveredRoot.dispatch("scroll");
coveredDocument.defaultView.flushAnimationFrame();
assert.deepEqual(coveredRequests, []);
assert.deepEqual(coveredActivations, []);
assert.equal(coveredRoot.scrollTop, 4 * ROW_H);
assert.equal(
  coveredRoot.getAttribute("aria-activedescendant"),
  treeItems(coveredRoot)[4].id,
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
boundaryTree.commitWindow(boundaryInitial, fixtureWindow(0, 4));
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
boundaryTree.commitWindow(boundaryReset, fixtureWindow(4, 4));
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
throwingRequestTree.commitWindow(
  throwingRequestInitial,
  fixtureWindow(0, 4),
);
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
atomicTree.commitWindow(atomicInitial, fixtureWindow(0, 2));
atomicDocument.defaultView.flushAnimationFrame();
atomicRoot.scrollTop = ROW_H;
const atomicGeneration = atomicTree.beginWindowRequest();
const atomicFingerprint = fingerprint(atomicRoot);
const atomicActiveDescendant = atomicRoot.getAttribute("aria-activedescendant");
const atomicActiveFlags = treeItems(atomicRoot).map(
  (element) => element.dataset.active ?? null,
);
const malformedRow = new Proxy(fixtureViews.maximum.rows[1], {
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
    total: fixtureViews.maximum.total,
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
assert.equal(
  atomicTree.commitWindow(atomicGeneration, fixtureWindow(1, 2)),
  true,
);

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
intentTree.commitWindow(intentInitial, fixtureWindow(0, 4));
intentDocument.defaultView.flushAnimationFrame();
intentRoot.scrollTop = ROW_H;
intentRoot.dispatch("scroll");
intentDocument.defaultView.flushAnimationFrame();
const passiveIntentRequest = intentRequests.at(-1);
assert.equal(passiveIntentRequest.index, 4);
dispatchKey(intentRoot, "Enter");
assert.deepEqual(intentActivations, [fixtureNodeIds.projection]);
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
programTree.commitWindow(programInitial, fixtureWindow(0, 8));
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
assert.equal(
  programTree.commitWindow(programKeyboard.generation, fixtureViews.tail),
  true,
);

const shortDocument = new TestDocument();
const shortRoot = shortDocument.createElement("div");
shortRoot.clientHeight = ROW_H - 1;
const shortTree = createTree(shortRoot);
const shortGeneration = shortTree.beginWindowRequest();
shortTree.commitWindow(shortGeneration, fixtureWindow(0, 1));
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
narrowTree.commitWindow(narrowInitial, fixtureWindow(0, 4));
narrowDocument.defaultView.flushAnimationFrame();
narrowRoot.scrollTop = 4 * ROW_H;
narrowRoot.dispatch("scroll");
narrowDocument.defaultView.flushAnimationFrame();
assert.deepEqual(narrowRequests, [{index: 7, generation: 2}]);
narrowRoot.dispatch("scroll");
assert.equal(narrowDocument.defaultView.animationFrames.length, 1);
assert.equal(narrowTree.commitWindow(2, fixtureWindow(7, 1)), true);
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
changedTree.commitWindow(changedInitial, fixtureWindow(0, 4));
changedDocument.defaultView.flushAnimationFrame();
changedRoot.scrollTop = 4 * ROW_H;
changedRoot.dispatch("scroll");
changedDocument.defaultView.flushAnimationFrame();
assert.deepEqual(changedRequests, [{index: 7, generation: 2}]);
changedRoot.scrollTop = 8 * ROW_H;
changedRoot.dispatch("scroll");
assert.equal(changedTree.commitWindow(2, fixtureWindow(7, 1)), true);
changedDocument.defaultView.flushAnimationFrame();
assert.deepEqual(changedRequests, [
  {index: 7, generation: 2},
  {index: 11, generation: 3},
]);
assert.equal(changedTree.commitWindow(3, fixtureWindow(8, 4)), true);
assert.equal(changedDocument.defaultView.animationFrames.length, 0);
assert.equal(changedRoot.scrollTop, 8 * ROW_H);

const unmeasuredRoot = new TestDocument().createElement("div");
unmeasuredRoot.scrollTop = 17;
const unmeasuredTree = createTree(unmeasuredRoot);
const unmeasuredGeneration = unmeasuredTree.beginWindowRequest();
unmeasuredTree.commitWindow(unmeasuredGeneration, fixtureWindow(5, 1));
assert.equal(unmeasuredRoot.scrollTop, 17);
unmeasuredRoot.clientHeight = ROW_H;
unmeasuredRoot.focus();
assert.equal(unmeasuredRoot.scrollTop, 5 * ROW_H);

// Arbitrary recycling cannot leave a stale active index or descendant.
const recycledGeneration = tree.beginWindowRequest();
assert.equal(
  tree.commitWindow(
    recycledGeneration,
    fixtureViews.tail,
    "missing-preferred",
  ),
  true,
);
const recycledActive = root.getAttribute("aria-activedescendant");
assert.ok(treeItems(root).some((element) => element.id === recycledActive));
dispatchKey(root, "ArrowRight");
assert.equal(root.getAttribute("aria-activedescendant"), recycledActive);

const emptyGeneration = tree.beginWindowRequest();
assert.equal(tree.commitWindow(emptyGeneration, fixtureViews.empty), true);
assert.equal(root.getAttribute("aria-activedescendant"), null);
assert.equal(treeItems(root).length, 0);
root.focus();
assert.equal(root.getAttribute("aria-activedescendant"), null);
dispatchUnconsumedKey(root, "Home");
assert.deepEqual(requested, [fixtureViews.maximum.total - 1, 0]);
const repopulatedGeneration = tree.beginWindowRequest();
assert.equal(
  tree.commitWindow(repopulatedGeneration, fixtureViews.head),
  true,
);
assert.equal(
  root.getAttribute("aria-activedescendant"),
  treeItems(root)[0].id,
);

const offWindowEmptyGeneration = tree.beginWindowRequest();
assert.equal(tree.commitWindow(offWindowEmptyGeneration, {
  offset: fixtureViews.maximum.total,
  total: fixtureViews.maximum.total,
  rows: [],
}), true);
assert.equal(root.getAttribute("aria-activedescendant"), null);
root.focus();
dispatchKey(root, "Home");
assert.deepEqual(requested, [fixtureViews.maximum.total - 1, 0, 0]);
assert.equal(
  tree.commitWindow(requestedGeneration, fixtureViews.head),
  true,
);

const maximumGeneration = tree.beginWindowRequest();
assert.equal(
  tree.commitWindow(maximumGeneration, fixtureViews.maximum),
  true,
);
assert.equal(treeItems(root).length, 256);
assert.equal(root.children.length, 258);
assert.equal(
  treeItems(root).find(
    (element) => element.dataset.nodeId === fixtureNodeIds.layout_control,
  ).children[1].textContent,
  layoutFixtureRendered,
);
assert.equal(
  treeItems(root).find(
    (element) => element.dataset.nodeId === fixtureNodeIds.ordinary_unicode,
  ).children[1].textContent,
  fixtureViews.next.rows[0].display,
);
assert.equal(
  treeItems(root).find(
    (element) => element.dataset.nodeId === fixtureNodeIds.long_unicode,
  ).children[1].textContent,
  fixtureViews.next.rows[1].display,
);

const staleGeneration = tree.beginWindowRequest();
const committedFingerprint = fingerprint(root);
assert.equal(tree.commitWindow(maximumGeneration, unreadableWindow), false);
assert.equal(staleReads, 0);
assert.deepEqual(fingerprint(root), committedFingerprint);
assert.equal(staleGeneration, maximumGeneration + 1);

// This exhaustive vector remains deliberately renderer-local because a real
// Windows filename cannot carry every defended code point (notably NUL).
const sinkRoot = document.createElement("div");
const sinkTree = createTree(sinkRoot);
const sinkGeneration = sinkTree.beginWindowRequest();
assert.equal(sinkTree.commitWindow(sinkGeneration, {
  offset: 0,
  total: 3,
  rows: [
    localRow(0, "sink-layout", layoutDisplay),
    localRow(1, "sink-supplemental", supplementalDisplay),
    localRow(2, "sink-long", supplementalLongDisplay),
  ],
}), true);
const sinkRows = treeItems(sinkRoot);
assert.equal(sinkRows[0].children[1].textContent, layoutRendered);
assert.equal(sinkRows[1].children[1].textContent, supplementalDisplay);
assert.equal(sinkRows[2].children[1].textContent, supplementalLongDisplay);
assert.equal(
  sinkRows.some((rowElement) =>
    activeLayoutControlPattern.test(rowElement.children[1].textContent)),
  false,
);

process.stdout.write(`${JSON.stringify({
  fixture_schema: fixture.schema,
  fixture_sha256: fixtureSha256,
  fixture_size: fixtureBytes.length,
})}\n`);

function localRow(index, nodeId, display, options = {}) {
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

function fixtureWindow(offset, count) {
  const rows = fixtureViews.maximum.rows.slice(offset, offset + count);
  assert.equal(rows.length, count);
  return {
    offset,
    total: fixtureViews.maximum.total,
    rows,
  };
}

function visibleFilesystemText(value) {
  return value.replace(
    /[\u0000-\u001f\u007f-\u009f\u00ad\u061c\u200b\u200e-\u200f\u2028-\u202e\u2060-\u206f\ufeff\u27e6-\u27e7]/gu,
    (character) =>
      `⟦U+${character.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}⟧`,
  );
}

function assertTreeFixture(value) {
  assert.deepEqual(Object.keys(value).sort(), ["node_ids", "schema", "views"]);
  assert.equal(value.schema, "namisync-tree-window-fixture-v1");
  assert.deepEqual(Object.keys(value.node_ids).sort(), [
    "layout_control",
    "long_unicode",
    "ordinary_unicode",
    "projection",
  ]);
  assert.equal(new Set(Object.values(value.node_ids)).size, 4);
  for (const nodeId of Object.values(value.node_ids)) {
    assert.match(nodeId, /^node-[0-9a-f]{32}$/u);
  }
  assert.deepEqual(Object.keys(value.views).sort(), [
    "empty",
    "head",
    "layout_control",
    "maximum",
    "next",
    "pointer_collapsed",
    "pointer_expanded",
    "projected_empty",
    "tail",
  ]);
  const rowKeys = [
    "depth",
    "display",
    "expanded",
    "first_child_visible_index",
    "is_container",
    "node_id",
    "parent_visible_index",
    "position_in_set",
    "set_size",
    "visible_index",
  ];
  for (const windowValue of Object.values(value.views)) {
    assert.deepEqual(Object.keys(windowValue).sort(), ["offset", "rows", "total"]);
    assert.ok(windowValue.rows.length <= 256);
    for (const [relativeIndex, rowValue] of windowValue.rows.entries()) {
      assert.deepEqual(Object.keys(rowValue).sort(), rowKeys);
      assert.equal(rowValue.visible_index, windowValue.offset + relativeIndex);
      assert.match(rowValue.node_id, /^node-[0-9a-f]{32}$/u);
    }
  }
  assert.equal(value.views.empty.total, 0);
  assert.deepEqual(value.views.empty.rows, []);
  assert.equal(value.views.maximum.rows.length, 256);
  assert.ok(value.views.maximum.total > 256);
  assert.equal(
    value.views.tail.rows.at(-1).visible_index,
    value.views.tail.total - 1,
  );
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

function dispatchUnconsumedKey(element, key) {
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
  assert.equal(prevented, false);
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
