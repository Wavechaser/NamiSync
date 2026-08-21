"""Static invariants over the exact wheel-shipped frontend file set."""

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from html.parser import HTMLParser
from pathlib import Path

import pytest

from conftest import BuiltWheel

from _tree_window_fixture import (
    TREE_WINDOW_FIXTURE_SCHEMA,
    TreeWindowFixture,
)

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityReason,
    IntegrityResult,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.session import (
    Disposition,
    PhaseStatus,
    SessionState,
    TERMINAL_STATES,
)
from namisync.interfaces.web.commands import production_command_specs
from namisync.workflows.views import ResultCategory

from _frontend_test_support import ASSET_ROOT, INITIAL_ASSETS, _node_executable


CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'none'; frame-src 'none'; "
    "object-src 'none'; base-uri 'none'; form-action 'none'"
)
PROJECT_ROOT = Path(__file__).parents[3]
_FORBIDDEN_ACTIVE_SINKS = (
    r"\b(?:innerHTML|outerHTML)\s*=",
    r"\.insertAdjacentHTML\s*\(",
    r"\bdocument\.write(?:ln)?\s*\(",
    r"\bsrcdoc\s*=",
    r"\bDOMParser\s*\(",
    r"\bcreateContextualFragment\s*\(",
    r"\.(?:href|src|style|cssText|on\w+)\s*=",
    r"\beval\s*\(",
    r"\bnew\s+Function\s*\(",
    r"\bset(?:Timeout|Interval)\s*\(\s*[\"']",
)


def _active_sink_hits(source: str) -> tuple[str, ...]:
    pattern_hits = tuple(
        pattern
        for pattern in _FORBIDDEN_ACTIVE_SINKS
        if re.search(pattern, source, re.IGNORECASE)
    )
    return pattern_hits + tuple(
        f"setAttribute:{name}" for name in _attribute_sink_hits(source)
    )


def _attribute_sink_hits(source: str) -> tuple[str, ...]:
    calls = re.findall(r"\.setAttribute\s*\(", source)
    fixed_names = re.findall(
        r"\.setAttribute\s*\(\s*['\"]([^'\"]+)['\"]\s*,",
        source,
    )
    if len(calls) != len(fixed_names):
        return ("dynamic-attribute-name",)
    allowed = {"aria-activedescendant", "role"}
    return tuple(name for name in fixed_names if name not in allowed)


def _javascript_frozen_array(source: str, name: str) -> tuple[str, ...]:
    match = re.search(
        rf"const {re.escape(name)} = Object\.freeze\((\[[\s\S]*?\])\);",
        source,
    )
    assert match is not None, name
    value = json.loads(re.sub(r",\s*]", "]", match.group(1)))
    assert isinstance(value, list)
    assert all(isinstance(item, str) for item in value)
    return tuple(value)


def _javascript_frozen_set(source: str, name: str) -> tuple[str, ...]:
    match = re.search(
        rf"const {re.escape(name)} = Object\.freeze\(new Set\((\[[\s\S]*?\])\)\);",
        source,
    )
    assert match is not None, name
    value = json.loads(re.sub(r",\s*]", "]", match.group(1)))
    assert isinstance(value, list)
    assert all(isinstance(item, str) for item in value)
    return tuple(value)


class _DocumentAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.head_elements: list[tuple[str, dict[str, str | None]]] = []
        self.inline_event_attributes: list[str] = []
        self.script_sources: list[str | None] = []
        self.stylesheet_sources: list[str | None] = []
        self.in_script = False
        self.inline_script_text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag == "head":
            self.in_head = True
        elif self.in_head:
            self.head_elements.append((tag, attributes))
        self.inline_event_attributes.extend(
            name for name, _ in attrs if name.casefold().startswith("on")
        )
        if tag == "script":
            self.in_script = True
            self.script_sources.append(attributes.get("src"))
        elif tag == "link" and attributes.get("rel") == "stylesheet":
            self.stylesheet_sources.append(attributes.get("href"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.in_head = False
        elif tag == "script":
            self.in_script = False

    def handle_data(self, data: str) -> None:
        if self.in_script and data.strip():
            self.inline_script_text.append(data)


def _wheel_assets(wheel: BuiltWheel) -> dict[str, str]:
    with zipfile.ZipFile(wheel.path) as archive:
        return {
            name.removeprefix(ASSET_ROOT): archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.startswith(ASSET_ROOT) and not name.endswith("/")
        }


def test_shipped_page_has_exact_first_csp_and_no_inline_execution(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    assert set(assets) == INITIAL_ASSETS
    assert assets["index.html"].isascii()
    raw_csp = re.search(
        r'<head><meta http-equiv="Content-Security-Policy" content="([^"]+)">',
        assets["index.html"],
    )
    assert raw_csp is not None
    assert raw_csp.group(1) == CSP
    parser = _DocumentAudit()
    parser.feed(assets["index.html"])

    first_tag, first_attrs = parser.head_elements[0]
    assert first_tag == "meta"
    assert first_attrs == {
        "http-equiv": "Content-Security-Policy",
        "content": CSP,
    }
    csp_elements = [
        attrs
        for tag, attrs in parser.head_elements
        if tag == "meta"
        and (attrs.get("http-equiv") or "").casefold()
        == "content-security-policy"
    ]
    assert csp_elements == [first_attrs]
    assert parser.inline_event_attributes == []
    assert parser.inline_script_text == []
    assert parser.stylesheet_sources == [
        "/tokens.css",
        "/components.css",
        "/app.css",
    ]
    assert parser.script_sources == ["/app.js"]


def test_br_g_32_only_bridge_wrapper_references_pywebview(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    references = {
        name for name, text in assets.items() if "window.pywebview" in text
    }

    assert references == {"bridge.js"}
    assert assets["bridge.js"].count("window.pywebview") == 1


def test_modules_use_only_local_explicit_js_imports(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    imports = {
        name: re.findall(r"\bfrom\s+[\"']([^\"']+)[\"']", text)
        for name, text in assets.items()
        if name.endswith(".js")
    }

    assert imports == {
        "app.js": [
            "./bridge.js",
            "./readiness.js",
            "./appearance.js",
            "./theme.js",
            "./panels.js",
            "./rail.js",
            "./render.js",
        ],
        "appearance.js": [],
        "bridge.js": [],
        "file_row.js": ["./render.js"],
        "icons.js": [],
        "integrity.js": ["./file_row.js", "./render.js"],
        "panels.js": ["./render.js"],
        "plan.js": ["./file_row.js", "./render.js"],
        "rail.js": ["./render.js"],
        "readiness.js": [],
        "render.js": [],
        "theme.js": ["./bridge.js", "./render.js"],
        "tree.js": ["./render.js"],
    }
    assert all(
        value.startswith("./") and value.endswith(".js")
        for values in imports.values()
        for value in values
    )
    assert all("innerHTML" not in text for text in assets.values())


def test_renderer_assets_stay_within_the_admitted_webview2_api_floor(
    built_wheel: BuiltWheel,
) -> None:
    javascript = "\n".join(
        source
        for name, source in _wheel_assets(built_wheel).items()
        if name.endswith(".js")
    )

    assert "Object.hasOwn(" not in javascript
    assert "crypto.randomUUID" not in javascript
    assert re.search(r"\.role\s*=", javascript) is None
    assert javascript.count(
        "new document.defaultView.ResizeObserver("
    ) == 1


def test_br_g_32_packaged_assets_exclude_active_markup_and_code_sinks(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    source = "\n".join(assets.values())

    assert _active_sink_hits(source) == ()
    assert _attribute_sink_hits(source) == ()
    assert source.count('setAttribute("aria-activedescendant",') == 2

    appearance = assets["appearance.js"]
    assert {
        name
        for name, source in assets.items()
        if "root.dataset.theme =" in source
    } == {"appearance.js"}
    assert "setAttribute" not in appearance
    assert ".style =" not in appearance
    assert ".cssText" not in appearance
    assert ".postMessage" not in appearance
    assert appearance.count("root.style.setProperty(") == 4
    assert appearance.count('addEventListener("message", receive)') == 1
    assert appearance.count('removeEventListener("message", receive)') == 1
    properties = re.findall(
        r'root\.style\.setProperty\(\s*"(--[a-z-]+)"', appearance
    )
    assert properties == [
        "--color-accent-fill",
        "--color-accent-fill-hover",
        "--color-accent-fill-pressed",
        "--color-accent-fill-foreground",
    ]

    tokens = assets["tokens.css"]
    assert tokens.count(':root[data-window-material="mica"]') == 1
    assert ':root[data-window-material="degraded"]' not in tokens
    mica = tokens.split(':root[data-window-material="mica"]', 1)[1]
    assert "--color-window-base: transparent;" in mica.split("}", 1)[0]


def test_static_sink_guard_rejects_dynamic_and_authority_attributes() -> None:
    assert _attribute_sink_hits('node.setAttribute(name, value);') == (
        "dynamic-attribute-name",
    )
    assert _attribute_sink_hits('node.setAttribute("href", value);') == (
        "href",
    )
    assert _attribute_sink_hits(
        'node.setAttribute("aria-activedescendant", value);'
    ) == ()


@pytest.mark.supplemental_node
def test_supplemental_node_appearance_receiver_accepts_latest_envelope() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental appearance probe")
    completed = subprocess.run(
        [
            str(node),
            str(PROJECT_ROOT / "tests" / "assets" / "appearance_probe.mjs"),
            str(PROJECT_ROOT / "namisync" / "interfaces" / "web" / "assets" / "appearance.js"),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result == {
        "revision": 7,
        "dataset": {
            "theme": "light",
            "highContrast": "false",
            "windowMaterial": "degraded",
        },
        "properties": {
            "--color-accent-fill": "#123456",
            "--color-accent-fill-hover": "#123456E6",
            "--color-accent-fill-pressed": "#123456CC",
            "--color-accent-fill-foreground": "#FFFFFF",
        },
        "resolvedBeforeValidMessage": False,
        "resolvedAfterValidMessage": True,
        "resolvedBeforeNewRevision": False,
        "resolvedAfterNewRevision": True,
        "observerCalls": 2,
        "listenerRemoved": True,
    }


@pytest.mark.supplemental_node
def test_supplemental_node_readiness_receiver_buffers_exact_envelopes() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental readiness probe")
    completed = subprocess.run(
        [
            str(node),
            str(PROJECT_ROOT / "tests" / "assets" / "readiness_probe.mjs"),
            str(
                PROJECT_ROOT
                / "namisync"
                / "interfaces"
                / "web"
                / "assets"
                / "readiness.js"
            ),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok"


@pytest.mark.supplemental_node
def test_supplemental_node_startup_rearms_per_bridge_generation() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental startup probe")
    completed = subprocess.run(
        [
            str(node),
            str(PROJECT_ROOT / "tests" / "assets" / "app_startup_probe.mjs"),
            str(
                PROJECT_ROOT
                / "namisync"
                / "interfaces"
                / "web"
                / "assets"
                / "app.js"
            ),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok"


@pytest.mark.supplemental_node
def test_supplemental_node_theme_selector_reconciles_authoritative_state() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental theme probe")
    completed = subprocess.run(
        [
            str(node),
            str(PROJECT_ROOT / "tests" / "assets" / "theme_selector_probe.mjs"),
            str(
                PROJECT_ROOT
                / "namisync"
                / "interfaces"
                / "web"
                / "assets"
                / "theme.js"
            ),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok"


@pytest.mark.supplemental_node
def test_supplemental_node_shared_test_bootstrap_is_generation_bound() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental test bootstrap probe")
    completed = subprocess.run(
        [
            str(node),
            str(
                PROJECT_ROOT
                / "tests"
                / "assets"
                / "bootstrap_test_bridge_probe.mjs"
            ),
            str(
                PROJECT_ROOT
                / "tests"
                / "assets"
                / "bootstrap_test_bridge.js"
            ),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok"


def test_br_g_32_production_inert_text_helper_owns_text_writes(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    renderer = assets["render.js"]
    file_row = assets["file_row.js"]
    integrity = assets["integrity.js"]
    plan = assets["plan.js"]
    tree = assets["tree.js"]

    text_assignments = {
        name: len(re.findall(r"\.textContent\s*=(?!=)", source))
        for name, source in assets.items()
        if name.endswith(".js")
    }
    assert sum(text_assignments.values()) == 1
    assert {
        name: count for name, count in text_assignments.items() if count
    } == {"render.js": 1}
    assert renderer.count(".textContent =") == 1
    assert "element.textContent = text;" in renderer
    assert 'import { renderText } from "./render.js";' in assets["app.js"]
    assert 'renderText(status, "Ready");' in assets["app.js"]
    assert re.search(r"\.textContent\s*=(?!=)", assets["app.js"]) is None
    assert "export function renderFilesystemText(element, text)" in renderer
    assert (
        r"/[\u0000-\u001f\u007f-\u009f\u00ad\u061c\u200b"
        r"\u200e-\u200f\u2028-\u202e\u2060-\u206f\ufeff"
        r"\u27e6-\u27e7]/gu;"
    ) in renderer
    assert "`⟦U+${character.codePointAt(0)" in renderer
    assert "renderText(element, visibleText);" in renderer
    assert (
        'import { renderFilesystemText } from "./render.js";' in tree
    )
    assert "renderFilesystemText(label, row.display);" in tree
    assert "renderText(" not in tree
    assert len(re.findall(r"\bdisplay\b", tree)) == 3
    assert [
        line.strip() for line in tree.splitlines() if "row.display" in line
    ] == [
        "display: row.display,",
        "renderFilesystemText(label, row.display);",
    ]
    assert re.search(r"\.textContent\s*=(?!=)", tree) is None
    assert (
        'import { renderFilesystemText, renderText } from "./render.js";'
        in file_row
    )
    assert "renderFilesystemText(label, rowView.nameText);" in file_row
    assert "renderText(size, rowView.sizeText);" in file_row
    assert "renderText(notes, rowView.notesText);" in file_row
    assert 'intentLabel.className = "nami-file-state-label";' in plan
    assert "renderText(intentLabel, rowView.intentText);" in plan
    assert "intent.append(intentLabel);" in plan
    assert "renderText(checksum, rowView.checksumText);" in plan
    assert "renderText(cell, text);" in integrity
    assert 'label.className = "nami-file-state-label";' in integrity
    assert "renderText(label, text);" in integrity
    assert "cell.append(label);" in integrity
    assert re.search(r"\.textContent\s*=(?!=)", file_row) is None
    assert re.search(r"\.textContent\s*=(?!=)", integrity) is None
    assert re.search(r"\.textContent\s*=(?!=)", plan) is None


def test_plan_row_renderer_is_dormant_and_consumes_only_projected_views(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    file_row = assets["file_row.js"]
    integrity = assets["integrity.js"]
    plan = assets["plan.js"]
    layout = assets["app.css"]
    production_shell = "\n".join(
        assets[name] for name in ("index.html", "app.js", "panels.js", "rail.js")
    )

    assert re.findall(r"export function ([A-Za-z0-9_]+)\(", plan) == [
        "renderPlanRow"
    ]
    assert re.findall(r"export function ([A-Za-z0-9_]+)\(", integrity) == [
        "renderIntegrityRow"
    ]
    assert re.findall(r"export function ([A-Za-z0-9_]+)\(", file_row) == [
        "renderFileRow"
    ]
    assert '"./plan.js"' not in production_shell
    assert '"./integrity.js"' not in production_shell
    assert "renderPlanRow" not in production_shell
    dormant_renderers = "\n".join((file_row, plan, integrity))
    assert '"./bridge.js"' not in dormant_renderers
    assert not any(
        name in dormant_renderers
        for name in (
            "SyncPlan",
            "workflow",
            "dispatcher",
            "session",
            "dispatchInteractive",
            "IntegrityResult",
            "PlanOperation",
        )
    )
    assert ".slice(" not in dormant_renderers
    assert ".substring(" not in dormant_renderers
    assert ".split(" not in dormant_renderers
    assert _javascript_frozen_array(plan, "STRING_FIELDS") == (
        "selectionLabel",
        "nameText",
        "sizeText",
        "intentText",
        "intentKey",
        "checksumText",
        "notesText",
    )
    assert _javascript_frozen_set(plan, "INTENT_KEYS") == (
        "copy",
        "mkdir",
        "move",
        "recase",
        "update",
        "move_update",
        "trash",
        "delete",
        "noop",
        "error",
        "unsupported",
        "blocked",
    )
    assert _javascript_frozen_set(plan, "ROW_LIFECYCLE_KEYS") == (
        "executing",
        "completed",
    )
    assert "ROW_LIFECYCLE_KEYS.has(rowView.lifecycleKey)" in plan
    assert "intent.dataset.lifecycle = rowView.lifecycleKey;" in plan
    assert 'intent.dataset.intent = rowView.intentKey;' in plan
    assert "intentTone" not in plan
    assert "intentForm" not in plan
    assert ".dataset.form" not in plan
    assert 'intentLabel.className = "nami-file-state-label";' in plan
    assert "intent.append(intentLabel);" in plan
    assert 'element.setAttribute("role", "row");' in file_row
    assert plan.count('cell.setAttribute("role", "cell");') == 1
    assert integrity.count('cell.setAttribute("role", "cell");') == 1
    assert 'checkbox.type = "checkbox";' in file_row
    assert 'checkbox.indeterminate = rowView.mixed;' in file_row
    assert 'renderFileRow(element, rowView, {' in plan
    assert 'renderFileRow(element, rowView, {' in integrity
    assert _javascript_frozen_array(integrity, "STRING_FIELDS") == (
        "presenceText",
        "presenceStatus",
        "checksumText",
    )
    assert _javascript_frozen_set(integrity, "INTEGRITY_KEYS") == (
        "verified",
        "baselined",
        "unverified",
        "modified",
        "reappeared",
        "unsupported",
        "canceled",
        "missing",
        "mismatched",
        "error",
    )
    assert _javascript_frozen_set(integrity, "ROW_LIFECYCLE_KEYS") == (
        "verifying",
        "completed",
    )
    assert "ROW_LIFECYCLE_KEYS.has(rowView.lifecycleKey)" in integrity
    assert "INTEGRITY_KEYS.has(rowView.presenceStatus)" in integrity
    assert "cell.dataset.lifecycle = lifecycle;" in integrity
    assert "cell.dataset.integrity = integrity;" in integrity
    assert "presenceTone" not in integrity
    assert "presenceForm" not in integrity
    assert ".dataset.form" not in integrity
    assert 'label.className = "nami-file-state-label";' in integrity
    assert "cell.append(label);" in integrity
    assert '"integrityText"' not in integrity
    assert '"integrityStatus"' not in integrity
    assert '"nami-integrity-row__presence"' in integrity
    assert '"nami-integrity-row__checksum"' in integrity
    assert '"nami-integrity-row__integrity"' not in integrity
    assert 'element.replaceChildren(selection, name, size, ...details.cells, notes);' in file_row

    zebra = ".nami-file-list__body > .nami-file-row:nth-child(even)"
    assert zebra in layout
    assert ".nami-file-list__body > .nami-file-row[hidden]" in layout
    assert "display: none;" in layout
    assert layout.count("--nami-file-column-") == 12
    assert ".nami-file-list__column-resizer" in layout
    assert "cursor: col-resize;" in layout
    assert "repeating-linear-gradient" not in layout
    assert "repeating-radial-gradient" not in layout
    assert not re.search(r"\.nami-file-row__cell[^\{]*:nth-child", layout)
    assert not re.search(r"\.nami-file-list__header-cell[^\{]*:nth-child", layout)
    assert "background: initial;" in layout
    assert "--file-row-h: 24px;" in assets["tokens.css"]
    assert layout.count("block-size: var(--file-row-h);") == 2
    file_grid = re.search(
        r"(?ms)^\.nami-file-list__grid\s*\{(?P<body>.*?)^\}",
        layout,
    )
    assert file_grid is not None
    assert "min-inline-size: 48rem;" in file_grid.group("body")
    file_rows = re.search(
        r"(?ms)^\.nami-file-list__body > \.nami-file-row\s*"
        r"\{(?P<body>.*?)^\}",
        layout,
    )
    assert file_rows is not None
    assert "font-size: var(--font-size-caption);" in file_rows.group("body")
    assert "line-height: var(--line-height-caption);" in file_rows.group("body")
    assert "--nami-plan-preferred-foreground:" not in layout
    assert "var(--plan-intent-" not in layout
    assert "--palette-" not in layout
    assert "[data-status" not in layout
    assert ".nami-file-state-label" in layout
    for intent in ("delete", "error", "unsupported", "blocked"):
        assert f'[data-intent="{intent}"]' in layout
    for integrity_state in (
        "reappeared",
        "unsupported",
        "missing",
        "mismatched",
        "error",
    ):
        assert f'[data-integrity="{integrity_state}"]' in layout
    assert "block-size: 18px;" in layout
    assert re.search(
        r"(?ms)^\.nami-file-list__body\s*\{[^}]*min-(?:block-)?size",
        layout,
    ) is None


def test_sh_g_7_tree_geometry_and_static_ownership_are_exact(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    css = "\n".join(
        text for name, text in assets.items() if name.endswith(".css")
    )
    tree = assets["tree.js"]

    css_row_heights = re.findall(r"--row-h:\s*(\d+)px;", css)
    javascript_row_heights = re.findall(
        r"export const ROW_H\s*=\s*(\d+);",
        tree,
    )
    assert css_row_heights == ["28"]
    assert javascript_row_heights == ["28"]
    assert int(css_row_heights[0]) == int(javascript_row_heights[0])

    app_css = assets["app.css"]
    row_rule = re.search(r"\.nami-tree-row\s*\{([^}]+)\}", app_css)
    assert row_rule is not None
    declarations = row_rule.group(1)
    for required in (
        "animation: none;",
        "block-size: var(--row-h);",
        "box-sizing: border-box;",
        "margin-block: 0;",
        "max-block-size: var(--row-h);",
        "min-block-size: var(--row-h);",
        "overflow: hidden;",
        "transition: none;",
    ):
        assert required in declarations
    label_rule = re.search(
        r"\.nami-tree-row__label\s*\{([^}]+)\}",
        app_css,
    )
    assert label_rule is not None
    for required in (
        "min-inline-size: 0;",
        "overflow: hidden;",
        "text-overflow: ellipsis;",
        "unicode-bidi: isolate;",
        "white-space: nowrap;",
    ):
        assert required in label_rule.group(1)

    for forbidden in (
        "window.pywebview",
        '"./bridge.js"',
        "current_path",
        "rel_path",
        "canonical",
        "search",
        "filter",
        "collapse",
        "ancestor",
    ):
        assert forbidden not in tree
    assert "256" not in tree
    assert 'root.setAttribute("role", "tree");' in tree
    assert 'element.setAttribute("role", "treeitem");' in tree
    assert tree.count("root.tabIndex = 0;") == 1
    assert (
        'root.setAttribute("aria-activedescendant", activeElement.id);'
        in tree
    )
    assert 'root.removeAttribute("aria-activedescendant");' in tree
    assert "root.ariaActiveDescendant" not in tree
    assert ".scrollIntoView(" not in tree
    assert "root.clientHeight <= 0" in tree
    assert "setProgrammaticScrollTop(rowTop);" in tree
    assert "Math.max(rowBottom - root.clientHeight, 0)," in tree
    assert (
        'root.addEventListener("scroll", onScroll, {passive: true});'
        in tree
    )
    resize_observer = re.search(
        r"const resizeObserver = new document\.defaultView\.ResizeObserver\("
        r"\(\) => \{\s*scheduleViewportCheck\(\);\s*\}\);",
        tree,
    )
    assert resize_observer is not None
    assert tree.count("resizeObserver.observe(root);") == 1
    assert tree.count("resizeObserver.disconnect();") == 1
    assert 'addEventListener("resize"' not in tree
    assert "if (disposed || scrollFramePending)" in tree
    assert "if (!disposed)" in tree
    assert (
        "return Object.freeze({beginWindowRequest, commitWindow, dispose});"
        in tree
    )
    for event, listener in (
        ("keydown", "onKeyDown"),
        ("scroll", "onScroll"),
        ("focus", "onFocus"),
    ):
        assert f'root.removeEventListener("{event}", {listener});' in tree
    assert "requestIndex(visibleIndex, generation);" in tree
    assert 'disclosure.addEventListener("click", onDisclosureClick);' in tree
    assert "event.stopPropagation();" in tree
    assert ".slice(" not in tree
    assert "Object.keys(" not in tree
    assert "Reflect.ownKeys(" not in tree


@pytest.mark.supplemental_node
def test_supplemental_node_tree_probe_uses_production_modules(
    tree_window_fixture: TreeWindowFixture,
) -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental tree probe")
    probe = PROJECT_ROOT / "tests" / "assets" / "tree_probe.mjs"
    probe_source = probe.read_text(encoding="utf-8")
    asset_root = (
        PROJECT_ROOT / "namisync" / "interfaces" / "web" / "assets"
    )
    assert probe_source.count("localRow(") == 5
    assert "Array.from({length: 256}" not in probe_source
    assert "fixtureViews.maximum" in probe_source
    assert "fixtureViews.empty" in probe_source
    assert "fixtureViews.tail" in probe_source

    completed = subprocess.run(
        [
            str(node),
            str(probe),
            str(asset_root / "tree.js"),
            str(asset_root / "render.js"),
            str(tree_window_fixture.path.resolve()),
            tree_window_fixture.sha256,
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "fixture_schema": TREE_WINDOW_FIXTURE_SCHEMA,
        "fixture_sha256": tree_window_fixture.sha256,
        "fixture_size": tree_window_fixture.size,
    }


@pytest.mark.supplemental_node
def test_supplemental_node_inert_text_rejects_before_coercion() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental render probe")
    probe = PROJECT_ROOT / "tests" / "assets" / "render_text_probe.mjs"
    renderer = (
        PROJECT_ROOT
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "render.js"
    )

    completed = subprocess.run(
        [str(node), str(probe), str(renderer)],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "mutation",
    [
        "node.innerHTML = hostile;",
        "node.outerHTML=hostile;",
        'node.insertAdjacentHTML("beforeend", hostile);',
        "document.write(hostile);",
        "frame.srcdoc = hostile;",
        "new DOMParser().parseFromString(hostile, mime);",
        "range.createContextualFragment(hostile);",
        'node.setAttribute(name, hostile);',
        "link.href = hostile;",
        "image.src = hostile;",
        "node.style = hostile;",
        "node.cssText = hostile;",
        "node.onclick = hostile;",
        "eval(hostile);",
        "new Function(hostile);",
        'setTimeout("hostile()", 1);',
        'setInterval("hostile()", 1);',
    ],
)
def test_br_g_32_sink_scan_catches_counterexample_mutations(
    mutation: str,
) -> None:
    assert _active_sink_hits(mutation)


def test_br_g_32_browser_wrapper_owns_exact_ids_response_checks_and_retry() -> None:
    source = (
        PROJECT_ROOT
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "bridge.js"
    ).read_text(encoding="utf-8")

    assert "COMMAND_POLICY_CONTRACT.start_plan.timeout" in source
    assert "command_id: mintId()" in source
    assert "crypto.randomUUID" not in source
    assert "cryptography.getRandomValues(bytes);" in source
    assert "new Uint8Array(16)" in source
    assert 'byte.toString(16).padStart(2, "0")' in source
    assert source.count('"pick_folder"') == 2
    assert source.count('"start_plan"') == 2
    assert source.count("return await startPlanAttempt(payload);") == 2
    assert "new StartPlanUncertainError(submit)" in source
    assert "generation !== bridgeGeneration" in source
    assert 'typeof sourceId !== "string"' in source
    assert 'typeof targetId !== "string"' in source
    assert 'typeof value.id === "string"' in source
    assert 'typeof value.request_id === "string"' in source
    assert 'typeof value.session_id === "string"' in source
    assert "Object.getPrototypeOf(value) !== Object.prototype" in source
    assert source.index("const generation = bridgeGeneration;") < source.index(
        "const api = bridgeApi();",
        source.index("async function dispatchAttempt"),
    )
    assert "return dispatchAttempt(" in source
    assert "response.request_id !== requestId" in source


def test_browser_command_policy_is_an_exact_mirror_of_the_native_table() -> None:
    source = (
        PROJECT_ROOT
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "bridge.js"
    ).read_text(encoding="utf-8")
    match = re.search(
        r"const COMMAND_POLICY_JSON = `([\s\S]*?)`;",
        source,
    )
    assert match is not None
    browser_policy = json.loads(match.group(1))
    commands = production_command_specs(
        picker=lambda: None,
        slots=object(),  # type: ignore[arg-type]
        registry=object(),  # type: ignore[arg-type]
        cosmetics=object(),  # type: ignore[arg-type]
        shell_ready=lambda _generation: None,
        readiness_echo=lambda _generation, _challenge: False,
    )
    native_policy = {
        name: {
            "timeout": spec.timeout.value,
            "retry": spec.retry.value,
            "phase": spec.phase.value,
        }
        for name, spec in commands.items()
    }

    assert browser_policy == native_policy


def test_task_recovery_and_release_budgets_are_explicit() -> None:
    source = (
        PROJECT_ROOT
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "bridge.js"
    ).read_text(encoding="utf-8")

    assert "COMMAND_POLICY_CONTRACT.close_task.timeout" in source
    assert "COMMAND_POLICY_CONTRACT.release_terminal_session.timeout" in source
    assert "const DRAIN_RECOVERY_DELAYS_MS = Object.freeze([" in source
    assert "const SESSION_RELEASE_RECOVERY_DELAYS_MS = Object.freeze([100, 250, 500]);" in source
    assert "const TASK_CLOSE_RECOVERY_DELAYS_MS = Object.freeze([100, 250, 500]);" in source
    assert '"release_terminal_session"' in source
    assert '"close_task"' in source
    assert "beginTaskRelease(task);" in source


def test_br_g_32_pick_folder_uses_neutral_interactive_transport() -> None:
    source = (
        PROJECT_ROOT
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "bridge.js"
    ).read_text(encoding="utf-8")
    picker = source.split("export async function pickFolder(", 1)[1].split(
        "export function dispatchInteractive(", 1
    )[0]

    assert "return dispatchInteractive(" in picker
    assert "dispatchAttempt(" not in picker


def test_br_g_32_response_id_accepts_null_only_for_structured_failures() -> None:
    source = (
        PROJECT_ROOT
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "bridge.js"
    ).read_text(encoding="utf-8")
    validator = source.split("function validateResponse(", 1)[1].split(
        "function validatePickFolderResult(", 1
    )[0]

    success = validator.split("if (response.ok) {", 1)[1].split(
        "return response.result;", 1
    )[0]
    failure = validator.split("return response.result;", 1)[1]
    assert "response.request_id !== requestId" in success
    assert "response.request_id !== requestId && response.request_id !== null" in failure
    assert "response.request_id === null" not in success


def test_br_g_32_start_plan_deadline_includes_bridge_readiness() -> None:
    source = (
        PROJECT_ROOT
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "bridge.js"
    ).read_text(encoding="utf-8")
    attempt = source.split(
        "function createDispatchAttempt(", 1
    )[1].split("async function dispatchReadyAttempt(", 1)[0]
    ready_attempt = source.split(
        "async function dispatchReadyAttempt(", 1
    )[1].split("async function withDeadline(", 1)[0]

    assert "promise: withDeadline(" in attempt
    assert "dispatchReadyAttempt(" in attempt
    assert "waitUntilReady," in attempt
    assert "() => cancelAttempt(attempt)" in attempt
    assert "await whenBridgeReady();" not in attempt
    assert ready_attempt.index("await waitUntilReady();") < ready_attempt.index(
        "const generation = bridgeGeneration;"
    )


def test_br_g_33_browser_event_vocabulary_matches_python_owners() -> None:
    source = (
        PROJECT_ROOT
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "bridge.js"
    ).read_text(encoding="utf-8")

    expected = {
        "SESSION_STATES": tuple(item.value for item in SessionState),
        "TERMINAL_STATES": tuple(item.value for item in TERMINAL_STATES),
        "RECORDING_STATES": tuple(item.value for item in RecordingStatus),
        "DISPOSITIONS": tuple(item.value for item in Disposition),
        "PHASE_STATES": tuple(item.value for item in PhaseStatus),
        "OPERATION_OUTCOMES": tuple(item.value for item in Outcome),
        "INTEGRITY_MODES": tuple(item.value for item in IntegrityMode),
        "INTEGRITY_RESULTS": tuple(item.value for item in IntegrityResult),
        "INTEGRITY_REASONS": tuple(item.value for item in IntegrityReason),
        "READ_STRATEGIES": tuple(item.value for item in ReadStrategy),
        "RECORD_DISPOSITIONS": tuple(
            item.value for item in RecordDisposition
        ),
        "RESULT_HEADLINES": tuple(item.value for item in ResultCategory),
        "RESULT_INTEGRITY_STATES": (
            "mismatch",
            "incomplete",
            "not-run",
            "modified",
            "missing",
            "baselined",
            "verified",
        ),
    }

    for name, values in expected.items():
        actual = _javascript_frozen_array(source, name)
        assert len(actual) == len(values)
        assert set(actual) == set(values)


def test_br_g_36_browser_progress_validator_owns_the_expanded_exact_shape() -> None:
    source = (
        PROJECT_ROOT
        / "namisync"
        / "interfaces"
        / "web"
        / "assets"
        / "bridge.js"
    ).read_text(encoding="utf-8")
    validator = source.split("function validateProgress(value) {", 1)[1].split(
        "function validateOperationItem(value) {", 1
    )[0]

    for field_name in (
        "items_done",
        "items_total",
        "bytes_done",
        "bytes_total",
        "current_path",
        "item_id",
        "item_type",
        "item_bytes_done",
        "item_bytes_total",
    ):
        assert validator.count(f'"{field_name}"') >= 1
    assert 'value.item_type === "operation"' in validator
    assert 'value.item_type === "integrity"' in validator
    assert "isValidNonemptyText(value.item_id)" in validator
    assert "identityPresent &&" in validator
    assert "value.item_bytes_done <= value.item_bytes_total" in validator


def test_ready_transition_cannot_overwrite_a_native_close_status(
    built_wheel: BuiltWheel,
) -> None:
    app = _wheel_assets(built_wheel)["app.js"]

    assert "acknowledgeShellReady," in app
    assert "BridgeTransportError," in app
    assert "echoReadiness," in app
    assert "markBridgeOperational," in app
    assert "whenBridgeApiReady," in app
    assert app.index("installReadinessReceiver(") < app.index(
        "installAppearanceReceiver("
    )
    assert app.index("installThemeSelector(") < app.index(
        "installAppearanceReceiver("
    )
    assert app.index("installAppearanceReceiver(") < app.index(
        "app.append(createTaskRail(), createWorkPanel());"
    )
    startup = app.split("async function finishStartup(", 1)[1]
    assert startup.index("whenBridgeApiReady()") < startup.index(
        "acknowledgeShellReady()"
    )
    assert startup.index("acknowledgeShellReady()") < startup.index(
        "readiness.whenReceivedAfter(readinessBaseline)"
    )
    assert startup.index(
        "readiness.whenReceivedAfter(readinessBaseline)"
    ) < startup.index("echoReadiness(challenge)")
    assert startup.index("echoReadiness(challenge)") < startup.index(
        "markBridgeOperational()"
    )
    assert "for (let attempt = 0; attempt < 2 && !acknowledged;" in startup
    assert startup.count("echoReadiness(challenge)") == 1
    assert "error instanceof BridgeTransportError" in startup
    assert "attempt > 0" in startup
    assert "if (!acknowledged)" in startup
    assert "appearance.whenAppliedAfter" not in startup
    assert startup.index("markBridgeOperational()") < startup.index(
        "void theme.open();"
    )
    assert startup.index("void theme.open();") < startup.index(
        'renderText(status, "Ready");'
    )
    assert "await theme.open()" not in startup
    assert "void theme.refresh();" in app
    assert 'window.addEventListener("pywebviewready"' in app
    assert "theme.invalidate();" in app
    assert "startupRerunReadinessBaseline = readinessBaseline;" in app
    assert "readinessBaseline: rerunReadinessBaseline" in app
    assert "readinessBaseline = readiness.revision()," in app
    assert "rejectSupersededStartup?.(new StartupSupersededError());" in app
    assert "error instanceof BridgeTransportError" in app
    assert 'status.textContent === "Ready"' in app
    assert 'renderText(status, "Starting...");' in app
    assert 'status.textContent === "Starting..."' in app
    assert app.count('renderText(status, "Ready")') == 1


def test_sh_g_7_packaged_shell_is_accessible_honest_and_command_inert(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    index = assets["index.html"]
    app = assets["app.js"]
    rail = assets["rail.js"]
    panels = assets["panels.js"]
    shell = "\n".join((app, rail, panels))

    assert '<main id="app">' in index
    assert index.count('id="host-status"') == 1
    assert '<p id="host-status" role="status" aria-live="polite">' in index
    assert '<span class="nami-field__label" id="theme-mode-label">Theme</span>' in index
    assert '<div class="nami-combobox" data-value="system" id="theme-mode">' in index
    assert 'class="nami-combobox__trigger"' in index
    assert 'role="combobox"' in index
    assert 'aria-haspopup="listbox"' in index
    assert 'aria-controls="theme-options"' in index
    assert 'id="theme-options" role="listbox"' in index
    assert re.findall(
        r'class="nami-combobox__option"[^>]+data-value="([a-z]+)"[^>]*>.*?<span>([A-Za-z]+)</span>',
        index,
    ) == [("system", "System"), ("light", "Light"), ("dark", "Dark")]
    assert "<select" not in index
    assert '<main id="app" aria-live=' not in index
    assert 'ariaLabel = "Task navigation";' in rail
    assert 'renderText(heading, "Tasks");' in rail
    assert 'renderText(empty, "No tasks are available.");' in rail
    assert 'emptySlot.classList.add("nami-card", "nami-task-rail__empty-slot");' in rail
    assert 'ariaLabel = "Work area";' in panels
    assert 'panel.setAttribute("role", "region");' in panels
    assert 'renderText(heading, "Work area");' in panels
    assert 'renderText(empty, "No task selected.");' in panels
    assert "Task details will appear here when a task is available." in panels
    assert "tabIndex" not in rail
    assert "tabIndex" not in panels
    assert 'rail.classList.add("nami-task-rail");' in rail
    assert 'rail.classList.add("nami-card"' not in rail
    assert 'panel.classList.add("nami-card", "nami-work-panel");' in panels
    assert "app.append(createTaskRail(), createWorkPanel());" in app
    assert '"./plan.js"' not in app + panels
    assert '"./integrity.js"' not in app + panels
    assert "renderPlanRow" not in shell
    assert 'status.textContent === "Starting..."' in app

    theme = assets["theme.js"]
    assert "export function installThemeCombobox(root)" in theme
    assert "popup.style.inlineSize" in theme
    assert "window.innerHeight - popupBounds.height" in theme
    assert 'trigger.ariaExpanded = "true"' in theme
    assert 'root.dispatchEvent(new Event("change", { bubbles: true }))' in theme
    assert "select.disabled = true;" in theme
    assert "snapshot.revision < state.authoritative.revision" in theme
    assert "error instanceof BridgeTransportError" in theme
    assert "await reconcileAfterUncertainty(" in theme
    assert "expectedRevision," in theme
    assert "result.disposition === \"conflict\"" in theme
    assert "#host-status" not in theme

    assert "window.pywebview" not in shell
    assert '"./bridge.js"' not in rail + panels
    assert "dispatch(" not in rail + panels
    assert "innerHTML" not in shell
    assert re.search(r"\.textContent\s*=(?!=)", shell) is None
    assert not re.search(r"task-[0-9a-f]{32}", shell)
    assert not re.search(r"[0-9a-f]{32}", shell)


def test_sh_g_7_shell_layout_reflows_without_fixed_viewport_clipping(
    built_wheel: BuiltWheel,
) -> None:
    app_css = _wheel_assets(built_wheel)["app.css"]

    assert '"rail work"' in app_css
    assert "minmax(12rem, 18rem) minmax(0, 1fr)" in app_css
    assert "container-type: inline-size;" in app_css
    assert "@container (max-width: 48rem)" in app_css
    assert "@media (max-width: 48rem)" not in app_css
    assert '"rail"' in app_css and '"work"' in app_css
    assert "grid-template-columns: minmax(0, 1fr);" in app_css
    assert app_css.count("min-inline-size: 0;") >= 2
    assert "min-block-size: 100vh;" in app_css
    assert "height: 100vh" not in app_css
    assert "overflow: hidden" not in app_css.split(".nami-tree", 1)[0]
    assert "--palette-" not in app_css
