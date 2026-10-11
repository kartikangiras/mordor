from common.storage import LocalStorage


def test_local_storage_roundtrip(tmp_path):
    s = LocalStorage(tmp_path)
    s.put_json("runs/a/manifest.json", {"x": 1})
    s.put("runs/a/overlay/00.png", b"\x89PNG", "image/png")
    assert s.get_json("runs/a/manifest.json") == {"x": 1}
    assert s.get("missing") is None
    assert s.list("runs/a") == ["runs/a/manifest.json", "runs/a/overlay/00.png"]


def test_local_storage_rejects_escape(tmp_path):
    s = LocalStorage(tmp_path)
    import pytest

    with pytest.raises(ValueError):
        s.put("../evil", b"", "text/plain")
