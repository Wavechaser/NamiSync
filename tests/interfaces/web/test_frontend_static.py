"""Static invariants over the exact wheel-shipped frontend file set."""

from __future__ import annotations

import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path

import pytest

from conftest import BuiltWheel

from test_wheel_assets import ASSET_ROOT, INITIAL_ASSETS


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
    r"\.setAttribute\s*\(",
    r"\.(?:href|src|style|cssText|on\w+)\s*=",
    r"\beval\s*\(",
    r"\bnew\s+Function\s*\(",
    r"\bset(?:Timeout|Interval)\s*\(\s*[\"']",
)


def _active_sink_hits(source: str) -> tuple[str, ...]:
    return tuple(
        pattern
        for pattern in _FORBIDDEN_ACTIVE_SINKS
        if re.search(pattern, source, re.IGNORECASE)
    )


class _DocumentAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.head_elements: list[tuple[str, dict[str, str | None]]] = []
        self.inline_event_attributes: list[str] = []
        self.script_sources: list[str | None] = []
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
    imports = re.findall(
        r"\bfrom\s+[\"']([^\"']+)[\"']",
        "\n".join(text for name, text in assets.items() if name.endswith(".js")),
    )

    assert imports == ["./bridge.js"]
    assert all(value.startswith("./") and value.endswith(".js") for value in imports)
    assert all("innerHTML" not in text for text in assets.values())


def test_br_g_32_packaged_assets_exclude_active_markup_and_code_sinks(
    built_wheel: BuiltWheel,
) -> None:
    source = "\n".join(_wheel_assets(built_wheel).values())

    assert _active_sink_hits(source) == ()


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

    assert "const START_PLAN_TIMEOUT_MS = 30000;" in source
    assert "command_id: mintId()" in source
    assert source.count('"pick_folder"') == 1
    assert source.count('"start_plan"') == 1
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
        "async function dispatchAttempt(", 1
    )[1].split("async function dispatchReadyAttempt(", 1)[0]
    ready_attempt = source.split(
        "async function dispatchReadyAttempt(", 1
    )[1].split("async function withDeadline(", 1)[0]

    assert "return withDeadline(" in attempt
    assert (
        "dispatchReadyAttempt(request, requestId, validateResult, attempt)"
        in attempt
    )
    assert "() => cancelAttempt(attempt)" in attempt
    assert "await whenBridgeReady();" not in attempt
    assert ready_attempt.index("await whenBridgeReady();") < ready_attempt.index(
        "const generation = bridgeGeneration;"
    )
    assert '"pick_folder",\n    Object.freeze({ purpose })' in source
    assert "validatePickFolderResult,\n    null," in source


def test_ready_transition_cannot_overwrite_a_native_close_status(
    built_wheel: BuiltWheel,
) -> None:
    app = _wheel_assets(built_wheel)["app.js"]

    assert 'status.textContent === "Starting..."' in app
    assert app.count('status.textContent = "Ready"') == 1
