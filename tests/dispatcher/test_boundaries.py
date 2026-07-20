from __future__ import annotations

import importlib
import inspect


def test_dispatcher_public_symbols_are_domain_blind() -> None:
    forbidden = ("sync", "scan", "plan", "preflight", "execute", "verify", "baseline", "ingest")
    modules = (
        importlib.import_module("namisync.dispatcher"),
        importlib.import_module("namisync.dispatcher.contracts"),
        importlib.import_module("namisync.dispatcher.custody"),
        importlib.import_module("namisync.dispatcher.dispatcher"),
        importlib.import_module("namisync.dispatcher.event_bus"),
        importlib.import_module("namisync.dispatcher.store"),
    )
    symbols = {
        name.lower()
        for module in modules
        for name, value in vars(module).items()
        if not name.startswith("_") and (inspect.isclass(value) or inspect.isfunction(value))
    }
    assert not {
        symbol
        for symbol in symbols
        if any(word in symbol for word in forbidden)
    }
