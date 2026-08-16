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

class TestDocument {
  constructor() {
    this.activeElement = null;
    this.created = 0;
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
  requestIndex: (index) => {
    requested.push(index);
    requestedGeneration = tree.beginWindowRequest(index);
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
    "depth", "display", "expanded", "node_id",
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
  requestIndex: (index) => {
    pagedRequests.push(index);
    pagedGeneration = pagedTree.beginWindowRequest(index);
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
