"""Streaming Fernet framing for large backup archives.

The legacy backup format uses one whole-file Fernet token.  Large backups
cannot be produced that way without keeping both the ZIP and the encrypted
copy on local disk, so new remote backups use independently authenticated
Fernet frames instead.
"""
from __future__ import annotations

import base64
import hashlib
import io
import struct
from pathlib import Path
from typing import BinaryIO, Iterable

STREAM_FERNET_MAGIC = b"ISG-FERNET-STREAM-V1\n"
STREAM_FERNET_CHUNK_BYTES = 1024 * 1024
_MAX_FRAME_BYTES = 64 * 1024 * 1024
_FRAME_HEADER = struct.Struct(">I")


class StreamEncryptionError(ValueError):
    """The framed encrypted backup is malformed or cannot be decrypted."""


def _fernet_for_key(raw: str):
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _write_all(destination: BinaryIO, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = destination.write(payload[offset:])
        if written is None:
            written = len(payload) - offset
        if written <= 0:
            raise OSError("Encrypted backup output stopped accepting data.")
        offset += int(written)


class ChunkedFernetWriter:
    """Write a non-seekable plaintext stream as authenticated Fernet frames."""

    def __init__(
        self,
        destination: BinaryIO,
        raw_key: str,
        *,
        chunk_size: int = STREAM_FERNET_CHUNK_BYTES,
    ) -> None:
        self._destination = destination
        self._fernet = _fernet_for_key(raw_key)
        self._chunk_size = max(64 * 1024, int(chunk_size))
        self._buffer = bytearray()
        self._plain_position = 0
        self._finished = False
        _write_all(destination, STREAM_FERNET_MAGIC)

    def write(self, data) -> int:
        if self._finished:
            raise ValueError("Encrypted backup stream is already finished.")
        payload = bytes(data)
        if not payload:
            return 0
        self._buffer.extend(payload)
        self._plain_position += len(payload)
        while len(self._buffer) >= self._chunk_size:
            self._write_frame(bytes(self._buffer[: self._chunk_size]))
            del self._buffer[: self._chunk_size]
        return len(payload)

    def _write_frame(self, plaintext: bytes) -> None:
        token = self._fernet.encrypt(plaintext)
        if len(token) > _MAX_FRAME_BYTES:
            raise StreamEncryptionError("Encrypted backup frame is unexpectedly large.")
        _write_all(self._destination, _FRAME_HEADER.pack(len(token)))
        _write_all(self._destination, token)

    def flush(self) -> None:
        flush = getattr(self._destination, "flush", None)
        if callable(flush):
            flush()

    def finish(self) -> None:
        if self._finished:
            return
        if self._buffer:
            self._write_frame(bytes(self._buffer))
            self._buffer.clear()
        self.flush()
        self._finished = True

    def close(self) -> None:
        self.finish()

    def tell(self) -> int:
        # ZipFile writes offsets for the plaintext ZIP, not for the framed
        # encrypted representation.
        return self._plain_position

    def seekable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seek(self, *_args, **_kwargs):
        raise io.UnsupportedOperation("Encrypted backup stream is not seekable.")


def is_chunked_fernet_file(path: Path) -> bool:
    try:
        with Path(path).open("rb") as source:
            return source.read(len(STREAM_FERNET_MAGIC)) == STREAM_FERNET_MAGIC
    except OSError:
        return False


def _read_exact(source: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = int(size)
    while remaining > 0:
        chunk = source.read(remaining)
        if not chunk:
            raise StreamEncryptionError("Encrypted backup frame is truncated.")
        chunks.append(bytes(chunk))
        remaining -= len(chunk)
    return b"".join(chunks)


def decrypt_chunked_fernet_file(
    source_path: Path,
    raw_key_candidates: Iterable[str],
    destination_path: Path,
) -> None:
    """Decrypt all frames into a ZIP path, trying the known key candidates."""
    from cryptography.fernet import InvalidToken

    candidates = [str(key) for key in raw_key_candidates if str(key)]
    if not candidates:
        raise StreamEncryptionError("No backup encryption key is available.")

    last_error: Exception | None = None
    with Path(source_path).open("rb") as source:
        if source.read(len(STREAM_FERNET_MAGIC)) != STREAM_FERNET_MAGIC:
            raise StreamEncryptionError("Unknown encrypted backup stream format.")
        for raw_key in candidates:
            source.seek(len(STREAM_FERNET_MAGIC))
            try:
                with Path(destination_path).open("wb") as destination:
                    fernet = _fernet_for_key(raw_key)
                    while True:
                        header = source.read(_FRAME_HEADER.size)
                        if not header:
                            break
                        if len(header) != _FRAME_HEADER.size:
                            raise StreamEncryptionError(
                                "Encrypted backup frame header is truncated."
                            )
                        frame_size = _FRAME_HEADER.unpack(header)[0]
                        if frame_size <= 0 or frame_size > _MAX_FRAME_BYTES:
                            raise StreamEncryptionError(
                                "Encrypted backup frame size is invalid."
                            )
                        token = _read_exact(source, frame_size)
                        destination.write(fernet.decrypt(token))
                return
            except InvalidToken as exc:
                last_error = exc
                continue
            except StreamEncryptionError as exc:
                last_error = exc
                continue
    raise StreamEncryptionError("Encrypted backup stream could not be decrypted.") from last_error
