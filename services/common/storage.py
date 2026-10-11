"""Object storage with one interface and two backends: S3 when DATA_BUCKET is set, else a
local directory (LOCAL_DATA_DIR, default ./.data). Lets the whole Day-1 pipeline run on a
laptop with no AWS credentials and produce byte-identical artefacts."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_SHORT = "public, max-age=60"


class Storage:
    def put(self, key: str, body: bytes, content_type: str, cache_control: str | None = None) -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def list(self, prefix: str) -> list[str]:
        raise NotImplementedError

    # convenience -----------------------------------------------------------------------------
    def put_json(self, key: str, obj: Any, cache_control: str | None = None) -> None:
        self.put(key, json.dumps(obj, separators=(",", ":")).encode(), "application/json", cache_control)

    def get_json(self, key: str) -> Any | None:
        raw = self.get(key)
        return None if raw is None else json.loads(raw)

    def put_text(self, key: str, text: str, content_type: str = "text/plain") -> None:
        self.put(key, text.encode(), content_type)

    def get_text(self, key: str) -> str | None:
        raw = self.get(key)
        return None if raw is None else raw.decode()


class S3Storage(Storage):
    def __init__(self, bucket: str):
        from common.aws import client

        self.bucket = bucket
        self.s3 = client("s3")

    def put(self, key, body, content_type, cache_control=None):
        extra = {"CacheControl": cache_control} if cache_control else {}
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type, **extra)

    def get(self, key):
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.s3.exceptions.NoSuchKey:
            return None

    def list(self, prefix):
        keys: list[str] = []
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(o["Key"] for o in page.get("Contents", []))
        return keys


class LocalStorage(Storage):
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError(f"key escapes storage root: {key}")
        return p

    def put(self, key, body, content_type, cache_control=None):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)

    def get(self, key):
        p = self._path(key)
        return p.read_bytes() if p.is_file() else None

    def list(self, prefix):
        base = self._path(prefix)
        if not base.exists():
            return []
        paths = [base] if base.is_file() else [q for q in base.rglob("*") if q.is_file()]
        return sorted(str(q.relative_to(self.root)) for q in paths)


_STORAGE: Storage | None = None


def storage() -> Storage:
    global _STORAGE
    if _STORAGE is None:
        bucket = os.environ.get("DATA_BUCKET")
        if bucket:
            _STORAGE = S3Storage(bucket)
        else:
            root = os.environ.get("LOCAL_DATA_DIR", ".data")
            log.info("DATA_BUCKET unset: using local storage at %s", root)
            _STORAGE = LocalStorage(root)
    return _STORAGE


def reset() -> None:
    """Tests only."""
    global _STORAGE
    _STORAGE = None
