"""Minimal standard-library Chrome DevTools Protocol client for WebView2 pages."""

from __future__ import annotations

import base64
import itertools
import json
import os
import re
import socket
import struct
import time
from collections.abc import Callable, Collection
from pathlib import Path
from urllib.parse import urlparse


def connect_page(profile: Path, process_ids: Callable[[], Collection[int]], timeout: float) -> tuple["Session", dict]:
    """Attach through the fresh profile's own browser, after confirming Job ownership."""

    active_port = profile / "webview2" / "EBWebView" / "DevToolsActivePort"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            lines = active_port.read_text(encoding="ascii").splitlines()
        except FileNotFoundError:
            lines = []
        if len(lines) == 2:
            port = int(lines[0])
            if not 0 < port < 65536 or not re.fullmatch(r"/devtools/browser/[0-9a-fA-F-]+", lines[1]):
                raise ValueError("invalid profile DevTools endpoint")
            break
        time.sleep(0.25)
    else:
        raise TimeoutError("no DevTools endpoint in the launched profile")

    session = Session(f"ws://127.0.0.1:{port}{lines[1]}", timeout=120)
    try:
        browsers = [p["id"] for p in session.call("SystemInfo.getProcessInfo")["processInfo"] if p["type"] == "browser"]
        if len(browsers) != 1 or browsers[0] not in process_ids():
            raise RuntimeError("DevTools browser is outside the launched Job")
        while time.monotonic() < deadline:
            pages = []
            for target in session.call("Target.getTargets")["targetInfos"]:
                url = urlparse(target["url"])
                if (target["type"] == "page" and target["title"] == "NamiSync"
                        and url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"}
                        and url.path == "/index.html"):
                    pages.append(target["targetId"])
            if len(pages) > 1:
                raise RuntimeError("ambiguous packaged DevTools page")
            if pages:
                attached = session.call("Target.attachToTarget", targetId=pages[0], flatten=True)
                session._target_session = attached["sessionId"]
                return session, {"port": port, "browser_pid": browsers[0], "target_id": pages[0]}
            time.sleep(0.25)
        raise TimeoutError("no packaged DevTools page in the launched browser")
    except BaseException:
        session.close()
        raise


class Session:
    """One WebSocket connection; unsolicited events are discarded."""

    def __init__(self, ws_url: str, timeout: float = 60.0) -> None:
        url = urlparse(ws_url)
        if url.hostname != "127.0.0.1":
            raise ValueError("DevTools target must be loopback")
        self._sock = socket.create_connection((url.hostname, url.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self._sock.sendall((
            f"GET {url.path} HTTP/1.1\r\nHost: {url.hostname}:{url.port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode())
        header = b""
        while b"\r\n\r\n" not in header:
            chunk = self._sock.recv(1)
            if not chunk:
                raise ConnectionError("DevTools handshake closed")
            header += chunk
        if b" 101 " not in header.split(b"\r\n", 1)[0]:
            raise ConnectionError(header.decode(errors="replace"))
        self._ids = itertools.count(1)
        self._target_session: str | None = None

    def _exact(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = self._sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("DevTools socket closed")
            data += chunk
        return bytes(data)

    def _send(self, text: str) -> None:
        payload = text.encode()
        size = len(payload)
        header = bytearray([0x81])
        if size < 126:
            header.append(0x80 | size)
        elif size < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", size)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", size)
        mask = os.urandom(4)
        self._sock.sendall(bytes(header) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _receive(self) -> dict:
        message = bytearray()
        while True:
            first, second = self._exact(2)
            size = second & 0x7F
            if size == 126:
                size = struct.unpack(">H", self._exact(2))[0]
            elif size == 127:
                size = struct.unpack(">Q", self._exact(8))[0]
            payload = self._exact(size)
            opcode = first & 0x0F
            if opcode == 0x8:
                raise ConnectionError("DevTools socket closed by peer")
            if opcode in (0x9, 0xA):
                continue
            message += payload
            if first & 0x80:
                return json.loads(message.decode())

    def call(self, method: str, **params: object) -> dict:
        ident = next(self._ids)
        request = {"id": ident, "method": method, "params": params}
        if self._target_session is not None:
            request["sessionId"] = self._target_session
        self._send(json.dumps(request))
        while True:
            message = self._receive()
            if message.get("id") == ident:
                if message.get("sessionId") != self._target_session:
                    raise RuntimeError("unexpected DevTools response session")
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def evaluate(self, expression: str) -> object:
        result = self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in result:
            raise RuntimeError(f"page exception: {result['exceptionDetails']}")
        return result["result"].get("value")

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass
