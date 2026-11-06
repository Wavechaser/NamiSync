"""Minimal standard-library Chrome DevTools Protocol client for WebView2 pages."""

from __future__ import annotations

import base64
import itertools
import json
import os
import socket
import struct
import time
import urllib.request
from urllib.parse import urlparse


def wait_for_page(port: int, timeout: float) -> dict:
    """Return the first page target exposed on 127.0.0.1:port."""

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as response:
                pages = [target for target in json.load(response) if target.get("type") == "page"]
            if pages:
                return pages[0]
        except OSError:
            pass
        time.sleep(0.25)
    raise TimeoutError("no DevTools page target")


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
        self._send(json.dumps({"id": ident, "method": method, "params": params}))
        while True:
            message = self._receive()
            if message.get("id") == ident:
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
