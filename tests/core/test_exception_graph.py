from __future__ import annotations

import ast
import gc
from collections import Counter
from pathlib import Path
from weakref import ref

import pytest

from namisync.core.exception_graph import (
    retire_exception_graph,
    retired_failure_detail,
)
from namisync.core.session import FailureDetail


_TRACEBACK_DESCRIPTOR = BaseException.__traceback__
_CAUSE_DESCRIPTOR = BaseException.__cause__
_CONTEXT_DESCRIPTOR = BaseException.__context__


class _Retained:
    pass


class _HostileLifecycleDescriptor:
    def __init__(self, name: str) -> None:
        self._name = name

    def __get__(self, instance, owner):
        raise AssertionError(f"subclass {self._name} getter was invoked")

    def __set__(self, instance, value) -> None:
        raise AssertionError(f"subclass {self._name} setter was invoked")


class _HostileLifecycleError(RuntimeError):
    __traceback__ = _HostileLifecycleDescriptor("traceback")
    __cause__ = _HostileLifecycleDescriptor("cause")
    __context__ = _HostileLifecycleDescriptor("context")


class _HostileExceptionGroup(ExceptionGroup):
    __traceback__ = _HostileLifecycleDescriptor("traceback")
    __cause__ = _HostileLifecycleDescriptor("cause")
    __context__ = _HostileLifecycleDescriptor("context")
    exceptions = _HostileLifecycleDescriptor("exceptions")


def _captured_hostile_error() -> tuple[_HostileLifecycleError, ref[_Retained]]:
    retained = _Retained()
    retained_ref = ref(retained)
    try:
        raise ValueError("cause")
    except ValueError as cause:
        try:
            raise _HostileLifecycleError("failure") from cause
        except _HostileLifecycleError as error:
            return error, retained_ref


def test_retire_exception_graph_bypasses_hostile_lifecycle_descriptors() -> None:
    error, retained_ref = _captured_hostile_error()

    retire_exception_graph(error)
    gc.collect()

    assert _TRACEBACK_DESCRIPTOR.__get__(error, BaseException) is None
    assert _CAUSE_DESCRIPTOR.__get__(error, BaseException) is None
    assert _CONTEXT_DESCRIPTOR.__get__(error, BaseException) is None
    assert retained_ref() is None


def test_retire_exception_graph_retires_shared_nested_group_members() -> None:
    error, retained_ref = _captured_hostile_error()
    inner = _HostileExceptionGroup("inner", (error, error))
    fatal = KeyboardInterrupt("stop")
    root = BaseExceptionGroup(
        "root",
        (inner, fatal, inner),
    )
    retire_exception_graph(root)
    gc.collect()

    assert BaseExceptionGroup.exceptions.__get__(root, BaseExceptionGroup) == (
        inner,
        fatal,
        inner,
    )
    assert BaseExceptionGroup.exceptions.__get__(inner, BaseExceptionGroup) == (
        error,
        error,
    )
    for retired in (root, inner, error):
        assert _TRACEBACK_DESCRIPTOR.__get__(retired, BaseException) is None
        assert _CAUSE_DESCRIPTOR.__get__(retired, BaseException) is None
        assert _CONTEXT_DESCRIPTOR.__get__(retired, BaseException) is None
    assert retained_ref() is None


def test_retired_failure_detail_renders_once_and_retires_owned_graph() -> None:
    class SingleRenderError(_HostileLifecycleError):
        def __init__(self) -> None:
            super().__init__("failure")
            self.render_count = 0
            self.cause_was_live_during_render = False

        def __str__(self) -> str:
            self.render_count += 1
            self.cause_was_live_during_render = (
                _CAUSE_DESCRIPTOR.__get__(self, BaseException) is not None
            )
            if self.render_count > 1:
                raise AssertionError("failure rendered more than once")
            return "rendered failure"

    retained = _Retained()
    retained_ref = ref(retained)
    error = SingleRenderError()
    try:
        raise ValueError("cause")
    except ValueError as cause:
        error.private_graph = retained
        _CAUSE_DESCRIPTOR.__set__(error, cause)
    del retained

    detail = retired_failure_detail(error)
    gc.collect()

    assert detail == FailureDetail("SingleRenderError", "rendered failure")
    assert error.render_count == 1
    assert error.cause_was_live_during_render
    assert _TRACEBACK_DESCRIPTOR.__get__(error, BaseException) is None
    assert _CAUSE_DESCRIPTOR.__get__(error, BaseException) is None
    assert _CONTEXT_DESCRIPTOR.__get__(error, BaseException) is None
    assert retained_ref() is not None
    del error
    gc.collect()
    assert retained_ref() is None


def test_retired_failure_detail_retires_after_projection_failure() -> None:
    class RenderingError(RuntimeError):
        def __str__(self) -> str:
            raise LookupError("diagnostic failed")

    rendered = RenderingError()
    with pytest.raises(LookupError, match="diagnostic failed"):
        retired_failure_detail(rendered)
    assert _TRACEBACK_DESCRIPTOR.__get__(rendered, BaseException) is None
    assert _CAUSE_DESCRIPTOR.__get__(rendered, BaseException) is None
    assert _CONTEXT_DESCRIPTOR.__get__(rendered, BaseException) is None

    constructed, _retained_ref = _captured_hostile_error()
    with pytest.raises(TypeError, match="failure type name must be text"):
        retired_failure_detail(
            constructed,
            type_name=object(),  # type: ignore[arg-type]
        )
    assert _TRACEBACK_DESCRIPTOR.__get__(constructed, BaseException) is None
    assert _CAUSE_DESCRIPTOR.__get__(constructed, BaseException) is None
    assert _CONTEXT_DESCRIPTOR.__get__(constructed, BaseException) is None


def test_retired_failure_detail_retires_shared_nested_group_members() -> None:
    error, retained_ref = _captured_hostile_error()
    inner = _HostileExceptionGroup("inner", (error, error))
    root = BaseExceptionGroup("root", (inner, inner))

    detail = retired_failure_detail(root, type_name="NestedFailure")
    gc.collect()

    assert detail == FailureDetail(
        "NestedFailure",
        "root (2 sub-exceptions)",
    )
    for retired in (root, inner, error):
        assert _TRACEBACK_DESCRIPTOR.__get__(retired, BaseException) is None
        assert _CAUSE_DESCRIPTOR.__get__(retired, BaseException) is None
        assert _CONTEXT_DESCRIPTOR.__get__(retired, BaseException) is None
    assert retained_ref() is None


def test_retired_failure_detail_projects_logical_native_paths() -> None:
    native_path = r"\\?\C:\private\item.txt"
    logical_path = r"C:\private\item.txt"
    error = OSError(12_345, "native failure", native_path)

    detail = retired_failure_detail(error)

    assert detail.type_name == type(error).__name__
    assert repr(native_path) not in detail.message
    assert repr(logical_path) in detail.message


def _failure_detail_policy(
    source: str,
    relative_path: str,
) -> tuple[
    Counter[tuple[str, str]],
    set[tuple[str, str]],
    set[str],
]:
    """Return exact direct-construction drift, not a dataflow proof."""

    tree = ast.parse(source, filename=relative_path)
    direct: set[str] = set()
    star_import = False
    assignments: list[tuple[tuple[ast.expr, ...], ast.expr | None]] = []
    call_sites: list[tuple[str, ast.expr]] = []
    scopes: list[str] = []

    class Visitor(ast.NodeVisitor):
        def _visit_body(self, body: list[ast.stmt], name: str) -> None:
            scopes.append(name)
            for statement in body:
                self.visit(statement)
            scopes.pop()

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            nonlocal star_import
            session_module = (
                node.module == "namisync.core.session"
                or (node.level > 0 and node.module == "session")
            )
            if session_module:
                direct.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "FailureDetail"
                )
                if any(alias.name == "*" for alias in node.names):
                    star_import = True
                    direct.add("FailureDetail")

        def visit_Assign(self, node: ast.Assign) -> None:
            assignments.append((tuple(node.targets), node.value))
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            assignments.append(((node.target,), node.value))
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if node.name == "FailureDetail":
                direct.add(node.name)
            for outer in (
                *node.decorator_list,
                *node.bases,
                *(keyword.value for keyword in node.keywords),
                *getattr(node, "type_params", ()),
            ):
                self.visit(outer)
            self._visit_body(node.body, node.name)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            for decorator in node.decorator_list:
                self.visit(decorator)
            self.visit(node.args)
            if node.returns is not None:
                self.visit(node.returns)
            for type_parameter in getattr(node, "type_params", ()):
                self.visit(type_parameter)
            self._visit_body(node.body, node.name)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)  # type: ignore[arg-type]

        def visit_Lambda(self, node: ast.Lambda) -> None:
            self.visit(node.args)
            scopes.append("<lambda>")
            self.visit(node.body)
            scopes.pop()

        def visit_Call(self, node: ast.Call) -> None:
            call_sites.append((".".join(scopes) or "<module>", node.func))
            self.generic_visit(node)

    Visitor().visit(tree)

    rebindings: set[str] = set()
    changed = True
    while changed:
        changed = False
        for targets, value in assignments:
            aliases_failure_detail = (
                isinstance(value, ast.Name) and value.id in direct
            ) or (
                isinstance(value, ast.Attribute)
                and value.attr == "FailureDetail"
            )
            if not aliases_failure_detail:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in direct:
                    direct.add(target.id)
                    rebindings.add(target.id)
                    changed = True

    calls: Counter[tuple[str, str]] = Counter()
    for scope, called in call_sites:
        direct_call = isinstance(called, ast.Name) and called.id in direct
        module_call = (
            isinstance(called, ast.Attribute)
            and called.attr == "FailureDetail"
        )
        if direct_call or module_call:
            calls[(relative_path, scope)] += 1
    return (
        calls,
        {(relative_path, name) for name in rebindings},
        {relative_path} if star_import else set(),
    )


@pytest.mark.parametrize(
    ("source", "relative_path", "expected"),
    [
        pytest.param(
            """
from namisync.core.session import FailureDetail as Imported
from namisync.core import session as session_module
from .session import FailureDetail as Relative
Alias = Imported
Annotated: object = Relative
Transitive = Annotated

def imported():
    Imported("T", "message")

def assigned():
    Alias("T", "message")

def module_alias():
    session_module.FailureDetail("T", "message")

Qualified = session_module.FailureDetail
""",
            "fixture.py",
            (
                Counter({
                    ("fixture.py", "imported"): 1,
                    ("fixture.py", "assigned"): 1,
                    ("fixture.py", "module_alias"): 1,
                }),
                {
                    ("fixture.py", "Alias"),
                    ("fixture.py", "Annotated"),
                    ("fixture.py", "Transitive"),
                    ("fixture.py", "Qualified"),
                },
                set(),
            ),
            id="imports-and-aliases",
        ),
        pytest.param(
            """
from namisync.core.session import FailureDetail as Detail

def outer():
    @Detail("Decorator", "message")
    def inner(value=Detail("Default", "message")):
        Detail("Body", "message")
""",
            "nested.py",
            (
                Counter({
                    ("nested.py", "outer"): 2,
                    ("nested.py", "outer.inner"): 1,
                }),
                set(),
                set(),
            ),
            id="nested-functions",
        ),
        pytest.param(
            """
import namisync.core.session

def plain_import():
    namisync.core.session.FailureDetail("T", "message")

def outer():
    value = lambda default=namisync.core.session.FailureDetail(
        "Default", "message"
    ): namisync.core.session.FailureDetail("Body", "message")
""",
            "qualified.py",
            (
                Counter({
                    ("qualified.py", "plain_import"): 1,
                    ("qualified.py", "outer"): 1,
                    ("qualified.py", "outer.<lambda>"): 1,
                }),
                set(),
                set(),
            ),
            id="qualified-and-lambda",
        ),
        pytest.param(
            """
from namisync.core.session import FailureDetail as Detail

def annotated(
    value: Detail("Parameter", "message"),
) -> Detail("Return", "message"):
    Detail("Body", "message")

async def async_owner(value=Detail("Default", "message")):
    Detail("AsyncBody", "message")

@Detail("ClassDecorator", "message")
class Nested:
    value = Detail("ClassBody", "message")
""",
            "extended.py",
            (
                Counter({
                    ("extended.py", "<module>"): 4,
                    ("extended.py", "annotated"): 1,
                    ("extended.py", "async_owner"): 1,
                    ("extended.py", "Nested"): 1,
                }),
                set(),
                set(),
            ),
            id="async-class-and-annotations",
        ),
        pytest.param(
            "from namisync.core.session import *\n",
            "star.py",
            (Counter(), set(), {"star.py"}),
            id="star-import",
        ),
    ],
)
def test_failure_detail_call_guard_detects_import_and_assignment_aliases(
    source: str,
    relative_path: str,
    expected: tuple[
        Counter[tuple[str, str]],
        set[tuple[str, str]],
        set[str],
    ],
) -> None:
    assert _failure_detail_policy(source, relative_path) == expected


def test_direct_failure_detail_construction_has_exact_static_owners() -> None:
    project_root = Path(__file__).parents[2]
    package_root = project_root / "namisync"
    actual: Counter[tuple[str, str]] = Counter()
    rebindings: set[tuple[str, str]] = set()
    star_imports: set[str] = set()
    for path in package_root.rglob("*.py"):
        relative = path.relative_to(project_root).as_posix()
        source = path.read_text(encoding="utf-8")
        calls, bound_aliases, stars = _failure_detail_policy(source, relative)
        actual.update(calls)
        rebindings.update(bound_aliases)
        star_imports.update(stars)

    assert rebindings == set()
    assert star_imports == set()
    assert actual == Counter(
        {
            ("namisync/core/events.py", "terminal_summary_from_dict"): 1,
            ("namisync/core/exception_graph.py", "retired_failure_detail"): 1,
            ("namisync/core/session.py", "_snapshot_failure_detail"): 1,
            (
                "namisync/core/session.py",
                "run_session.boundary_failure_result",
            ): 1,
            ("namisync/db/history.py", "_validate_terminal_snapshot"): 1,
            (
                "namisync/dispatcher/dispatcher.py",
                "Dispatcher._complete_unstarted_attempt",
            ): 1,
            ("namisync/workflows/inventory.py", "run_integrity"): 1,
            ("namisync/workflows/inventory.py", "_refused_resolution"): 1,
            ("namisync/workflows/sync.py", "_run_execution"): 5,
            (
                "namisync/workflows/sync.py",
                "_settle_fresh_execute_boundary",
            ): 1,
            (
                "namisync/workflows/sync.py",
                "_close_recording_failure",
            ): 1,
        }
    )
