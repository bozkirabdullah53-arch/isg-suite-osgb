from pathlib import Path

import pytest

from app.services.object_store import LocalObjectStore
from app.services.remote_training_video_r2_backfill import (
    copy_video_inventory_to_remote,
)


class _Remote:
    def __init__(self, objects=None, *, fail_upload=False):
        self.objects = dict(objects or {})
        self.fail_upload = fail_upload
        self.uploads = []
        self.deleted = []

    def remote_size(self, key):
        content = self.objects.get(key)
        return None if content is None else len(content)

    def put_file(self, key, path: Path, *, content_type=None):
        if self.fail_upload:
            raise RuntimeError("simulated upload failure")
        self.objects[key] = path.read_bytes()
        self.uploads.append((key, content_type))
        return key

    def get_range(self, key, *, start, end):
        return self.objects[key][start : end + 1]

    def presigned_get_url(self, key, *, expires_in_seconds):
        assert key in self.objects
        assert expires_in_seconds == 300
        return "https://r2.example/temporary"

    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)


def _row(key, content, *, content_type="video/mp4"):
    return {
        "storage_key": key,
        "declared_size": len(content),
        "content_type": content_type,
    }


def test_backfill_copies_missing_objects_and_keeps_local_files(tmp_path):
    local = LocalObjectStore(tmp_path)
    first = b"a" * 200
    second = b"b" * 300
    local.put_bytes("videos/first.mp4", first)
    local.put_bytes("videos/second.mp4", second)
    remote = _Remote({"videos/second.mp4": second})

    result = copy_video_inventory_to_remote(
        [
            _row("videos/first.mp4", first),
            _row("videos/second.mp4", second),
        ],
        local=local,
        remote=remote,
    )

    assert result["status"] == "completed"
    assert result["copied"] == 1
    assert result["already_remote"] == 1
    assert result["pilot_range_read_verified"] is True
    assert result["presigned_read_verified"] is True
    assert result["local_files_deleted"] == 0
    assert result["database_rows_changed"] == 0
    assert remote.uploads == [("videos/first.mp4", "video/mp4")]
    assert (tmp_path / "videos/first.mp4").read_bytes() == first
    assert (tmp_path / "videos/second.mp4").read_bytes() == second


def test_backfill_never_overwrites_remote_size_conflict(tmp_path):
    local = LocalObjectStore(tmp_path)
    local.put_bytes("videos/conflict.mp4", b"local-content")
    local.put_bytes("videos/good.mp4", b"good-content" * 20)
    remote = _Remote({"videos/conflict.mp4": b"different"})

    result = copy_video_inventory_to_remote(
        [
            _row("videos/conflict.mp4", b"local-content"),
            _row("videos/good.mp4", b"good-content" * 20),
        ],
        local=local,
        remote=remote,
    )

    assert result["status"] == "completed_with_issues"
    assert result["conflict"] == 1
    assert remote.objects["videos/conflict.mp4"] == b"different"
    assert remote.objects["videos/good.mp4"] == b"good-content" * 20


def test_failed_pilot_stops_batch_without_deleting_local_files(tmp_path):
    local = LocalObjectStore(tmp_path)
    local.put_bytes("videos/first.mp4", b"first" * 40)
    local.put_bytes("videos/second.mp4", b"second" * 40)
    remote = _Remote(fail_upload=True)

    with pytest.raises(RuntimeError, match="İlk R2 video pilotu başarısız"):
        copy_video_inventory_to_remote(
            [
                _row("videos/first.mp4", b"first" * 40),
                _row("videos/second.mp4", b"second" * 40),
            ],
            local=local,
            remote=remote,
        )

    assert (tmp_path / "videos/first.mp4").is_file()
    assert (tmp_path / "videos/second.mp4").is_file()
    assert remote.objects == {}


def test_backfill_reports_missing_local_without_remote(tmp_path):
    result = copy_video_inventory_to_remote(
        [_row("videos/missing.mp4", b"expected")],
        local=LocalObjectStore(tmp_path),
        remote=_Remote(),
    )

    assert result["status"] == "completed_with_issues"
    assert result["missing_local"] == 1
    assert result["copied"] == 0
