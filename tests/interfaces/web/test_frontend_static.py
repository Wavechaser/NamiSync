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
            "./appearance.js",
            "./panels.js",
            "./rail.js",
            "./render.js",
        ],
        "appearance.js": [],
        "bridge.js": [],
        "icons.js": [],
        "panels.js": ["./render.js"],
        "rail.js": ["./render.js"],
        "render.js": [],
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


def test_br_g_32_packaged_assets_exclude_active_markup_and_code_sinks(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    source = "\n".join(assets.values())

    assert _active_sink_hits(source) == ()
    assert _attribute_sink_hits(source) == ()
    assert source.count('setAttribute("aria-activedescendant",') == 1

    appearance = assets["appearance.js"]
    assert "setAttribute" not in appearance
    assert ".style =" not in appearance
    assert ".cssText" not in appearance
    assert ".postMessage" not in appearance
    assert appearance.count("root.style.setProperty(") == 6
    assert appearance.count('addEventListener("message", receive)') == 1
    assert appearance.count('removeEventListener("message", receive)') == 1
    properties = re.findall(
        r'root\.style\.setProperty\(\s*"(--[a-z-]+)"', appearance
    )
    assert properties == [
        "--color-accent",
        "--color-accent-hover",
        "--color-accent-pressed",
        "--color-accent-foreground",
        "--color-accent-hover-foreground",
        "--color-accent-pressed-foreground",
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
        "revision": 6,
        "dataset": {
            "theme": "light",
            "highContrast": "false",
            "windowMaterial": "degraded",
        },
        "properties": {
            "--color-accent": "#123456",
            "--color-accent-hover": "#234567",
            "--color-accent-pressed": "#012345",
            "--color-accent-foreground": "#FFFFFF",
            "--color-accent-hover-foreground": "#FFFFFF",
            "--color-accent-pressed-foreground": "#FFFFFF",
        },
        "resolvedBeforeValidMessage": False,
        "resolvedAfterValidMessage": True,
        "resolvedBeforeNewRevision": False,
        "resolvedAfterNewRevision": True,
        "listenerRemoved": True,
    }


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


def test_br_g_32_production_inert_text_helper_owns_text_writes(
    built_wheel: BuiltWheel,
) -> None:
    assets = _wheel_assets(built_wheel)
    renderer = assets["render.js"]
    tree = assets["tree.js"]

    assert renderer.count(".textContent =") == 1
    assert "element.textContent = text;" in renderer
    assert 'import { renderText } from "./render.js";' in assets["app.js"]
    assert 'renderText(status, "Ready");' in assets["app.js"]
    assert re.search(r"\.textContent\s*=(?!=)", assets["app.js"]) is None
    assert 'import { renderText } from "./render.js";' in tree
    assert "renderText(label, row.display);" in tree
    assert re.search(r"\.textContent\s*=(?!=)", tree) is None


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
    assert ".slice(" not in tree
    assert "Object.keys(" not in tree
    assert "Reflect.ownKeys(" not in tree


@pytest.mark.supplemental_node
def test_supplemental_node_tree_probe_uses_production_modules() -> None:
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is unavailable for the supplemental tree probe")
    probe = PROJECT_ROOT / "tests" / "assets" / "tree_probe.mjs"
    asset_root = (
        PROJECT_ROOT / "namisync" / "interfaces" / "web" / "assets"
    )

    completed = subprocess.run(
        [
            str(node),
            str(probe),
            str(asset_root / "tree.js"),
            str(asset_root / "render.js"),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


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
        shell_ready=lambda _generation: None,
    )
    native_policy = {
        name: {
            "timeout": spec.timeout.value,
            "retry": spec.retry.value,
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


def test_ready_transition_cannot_overwrite_a_native_close_status(
    built_wheel: BuiltWheel,
) -> None:
    app = _wheel_assets(built_wheel)["app.js"]

    assert "acknowledgeShellReady," in app
    assert "BridgeTransportError," in app
    assert "markBridgeOperational," in app
    assert "whenBridgeApiReady," in app
    assert app.index("installAppearanceReceiver(") < app.index(
        "app.append(createTaskRail(), createWorkPanel());"
    )
    startup = app.split("async function finishStartup(", 1)[1]
    assert startup.index("whenBridgeApiReady()") < startup.index(
        "acknowledgeShellReady()"
    )
    assert startup.index("acknowledgeShellReady()") < startup.index(
        "appearance.whenAppliedAfter(appearanceBaseline)"
    )
    assert startup.index(
        "appearance.whenAppliedAfter(appearanceBaseline)"
    ) < startup.index("markBridgeOperational()")
    assert startup.index("markBridgeOperational()") < startup.index(
        'renderText(status, "Ready");'
    )
    assert 'window.addEventListener("pywebviewready"' in app
    assert "startupRerunRequested ||= rerun;" in app
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
    assert '<main id="app" aria-live=' not in index
    assert 'ariaLabel = "Task navigation";' in rail
    assert 'renderText(heading, "Tasks");' in rail
    assert 'renderText(empty, "No tasks are available.");' in rail
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
    assert 'status.textContent === "Starting..."' in app

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
    assert "@media (max-width: 48rem)" in app_css
    assert '"rail"' in app_css and '"work"' in app_css
    assert "grid-template-columns: minmax(0, 1fr);" in app_css
    assert app_css.count("min-inline-size: 0;") >= 2
    assert "min-block-size: 100vh;" in app_css
    assert "height: 100vh" not in app_css
    assert "overflow: hidden" not in app_css.split(".nami-tree", 1)[0]
    assert "--palette-" not in app_css
