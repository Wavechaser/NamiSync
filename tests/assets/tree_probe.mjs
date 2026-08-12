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
    this.value = "";
  }

  append(...children) {
    this.children.push(...children);
  }

  replaceChildren(...children) {
    this.children = [...children];
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
  createElement(tagName) {
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
assert.equal(
  treeSource.split(renderSpecifier).length - 1,
  1,
  "tree module must have one exact render import",
);
const linkedTreeSource = treeSource.replace(
  renderSpecifier,
  JSON.stringify(renderUrl),
);
const {ROW_H, createTree} = await import(dataModuleUrl(linkedTreeSource));

assert.equal(ROW_H, 28);
assert.throws(() => createTree({}), /tree root must be an Element/);

const document = new TestDocument();
const root = document.createElement("div");
root.ariaLabel = "Plan";
const tree = createTree(root);
assert.equal(root.role, "tree");
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
});
assert.equal(tree.commitWindow(firstGeneration, unreadableWindow), false);
assert.equal(staleReads, 0);
assert.equal(root.children[0], topSpacer);
assert.equal(root.children[1], bottomSpacer);

const hostileDisplay =
  "wave \u{1f30a} e\u0301 <img onerror=alert(1)> & \u6d77";
const longDisplay = `${"\u6ce2".repeat(600)} end`;
const accessedFields = new Set();
const trackedContainer = new Proxy(
  Object.freeze({
    node_id: "node-container",
    display: hostileDisplay,
    depth: 0,
    is_container: true,
    expanded: false,
  }),
  {
    get(target, property, receiver) {
      if (typeof property === "string") {
        accessedFields.add(property);
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
    Object.freeze({
      node_id: "node-leaf",
      display: longDisplay,
      depth: 1,
      is_container: false,
      expanded: false,
    }),
  ]),
});
assert.equal(tree.commitWindow(secondGeneration, firstWindow), true);
assert.deepEqual(
  [...accessedFields].sort(),
  ["depth", "display", "expanded", "is_container", "node_id"],
);
assert.equal(root.children.length, 4);
assert.equal(root.children[0], topSpacer);
assert.equal(root.children.at(-1), bottomSpacer);
assert.equal(topSpacer.style.blockSize, `${5 * ROW_H}px`);
assert.equal(bottomSpacer.style.blockSize, `${3 * ROW_H}px`);

const firstRows = treeItems(root);
assert.equal(firstRows.length, 2);
assert.equal(firstRows[0].dataset.nodeId, "node-container");
assert.equal(firstRows[0].role, "treeitem");
assert.equal(firstRows[0].ariaLevel, "1");
assert.equal(firstRows[0].ariaExpanded, "false");
assert.equal(
  firstRows[0].style.getPropertyValue("--nami-tree-depth"),
  "0",
);
assert.equal(firstRows[0].children[0].textContent, hostileDisplay);
assert.equal(firstRows[1].dataset.nodeId, "node-leaf");
assert.equal(firstRows[1].ariaLevel, "2");
assert.equal(firstRows[1].ariaExpanded, undefined);
assert.equal(firstRows[1].children[0].textContent, longDisplay);

const secondRoot = document.createElement("div");
secondRoot.ariaLabel = "Inventory";
const secondTree = createTree(secondRoot);
const independentGeneration = secondTree.beginWindowRequest();
assert.equal(independentGeneration, 1);
assert.equal(
  secondTree.commitWindow(independentGeneration, {
    offset: 0,
    total: 1,
    rows: [{
      node_id: "inventory-node",
      display: "Inventory row",
      depth: 0,
      is_container: false,
      expanded: false,
    }],
  }),
  true,
);
assert.equal(tree.commitWindow(secondGeneration, firstWindow), true);

const thirdGeneration = tree.beginWindowRequest();
const committedChildren = [...root.children];
const committedTopSize = topSpacer.style.blockSize;
const committedBottomSize = bottomSpacer.style.blockSize;
assert.equal(tree.commitWindow(secondGeneration, unreadableWindow), false);
assert.equal(staleReads, 0);
assert.equal(root.children.length, committedChildren.length);
for (let index = 0; index < committedChildren.length; index += 1) {
  assert.equal(root.children[index], committedChildren[index]);
}
assert.equal(topSpacer.style.blockSize, committedTopSize);
assert.equal(bottomSpacer.style.blockSize, committedBottomSize);

const maximumRows = Array.from({length: 256}, (_, index) => ({
  node_id: `node-${index}`,
  display: index === 255 ? longDisplay : `Row ${index}`,
  depth: index === 0 ? 0 : 1,
  is_container: index === 0,
  expanded: true,
}));
assert.equal(
  tree.commitWindow(thirdGeneration, {
    offset: 0,
    total: maximumRows.length,
    rows: maximumRows,
  }),
  true,
);
assert.equal(treeItems(root).length, 256);
assert.equal(root.children.length, 258);
assert.equal(root.children[0], topSpacer);
assert.equal(root.children.at(-1), bottomSpacer);
assert.equal(topSpacer.style.blockSize, "0px");
assert.equal(bottomSpacer.style.blockSize, "0px");
assert.equal(treeItems(root).at(-1).children[0].textContent, longDisplay);

const fourthGeneration = tree.beginWindowRequest();
assert.equal(
  tree.commitWindow(fourthGeneration, {offset: 999, total: 4, rows: []}),
  true,
);
assert.equal(treeItems(root).length, 0);
assert.equal(root.children.length, 2);
assert.equal(root.children[0], topSpacer);
assert.equal(root.children[1], bottomSpacer);
assert.equal(topSpacer.style.blockSize, `${4 * ROW_H}px`);
assert.equal(bottomSpacer.style.blockSize, "0px");

function assertSpacer(element) {
  assert.ok(element.classList.contains("nami-tree__spacer"));
  assert.equal(element.ariaHidden, "true");
  assert.notEqual(element.role, "treeitem");
}

function treeItems(element) {
  return element.children.filter((child) => child.role === "treeitem");
}

function dataModuleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}
