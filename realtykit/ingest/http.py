"""httpx client with ETag / Last-Modified and SHA256 file cache."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from realtykit.log import log, utc_iso
from realtykit.settings import Settings, get_settings

DEFAULT_TIMEOUT = 30.0
FRED_TIMEOUT = 8.0


@dataclass
class CachedFetch:
    path: Path
    status_code: int
    not_modified: bool
    etag: str | None
    last_modified: str | None
    content_sha256: str
    bytes: int
    fetched_at: str
    from_cache: bool


def _meta_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".meta.json")


def read_meta(path: Path) -> dict:
    meta = _meta_path(path)
    if not meta.exists():
        return {}
    return json.loads(meta.read_text(encoding="utf-8"))


def write_meta(path: Path, meta: dict) -> None:
    _meta_path(path).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_fallback(settings: Settings, filename: str) -> Path | None:
    candidate = settings.data / "probe" / filename
    return candidate if candidate.exists() else None


class CachedHttp:
    def __init__(self, settings: Settings | None = None, *, root: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.raw = root or self.settings.raw_dir
        self.raw.mkdir(parents=True, exist_ok=True)

    def _headers(self, extra: dict | None = None) -> dict[str, str]:
        headers = {"User-Agent": self.settings.user_agent, "Accept": "*/*"}
        if extra:
            headers.update(extra)
        return headers

    def dest(self, name: str) -> Path:
        path = self.raw / name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def head(self, url: str, *, timeout: float = DEFAULT_TIMEOUT) -> httpx.Response:
        with httpx.Client(
            timeout=timeout, follow_redirects=True, headers=self._headers()
        ) as client:
            return client.head(url)

    def get_cached(
        self,
        url: str,
        dest_name: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_bytes: int | None = None,
        force: bool = False,
        retries: int = 3,
        backoff: float = 1.5,
        extra_headers: dict | None = None,
        probe_name: str | None = None,
    ) -> CachedFetch:
        dest = self.dest(dest_name)
        meta = read_meta(dest)
        headers = self._headers(extra_headers)
        if not force and dest.exists():
            if meta.get("etag"):
                headers["If-None-Match"] = meta["etag"]
            if meta.get("last_modified"):
                headers["If-Modified-Since"] = meta["last_modified"]

        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                with (
                    httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client,
                    client.stream("GET", url) as resp,
                ):
                    if resp.status_code == 304 and dest.exists():
                        log("http_not_modified", url=url, dest=str(dest))
                        return CachedFetch(
                            path=dest,
                            status_code=304,
                            not_modified=True,
                            etag=meta.get("etag"),
                            last_modified=meta.get("last_modified"),
                            content_sha256=meta.get("content_sha256") or sha256_file(dest),
                            bytes=dest.stat().st_size,
                            fetched_at=utc_iso(),
                            from_cache=True,
                        )
                    resp.raise_for_status()
                    length = resp.headers.get("Content-Length")
                    if max_bytes and length and int(length) > max_bytes:
                        raise ValueError(f"object {int(length)} bytes exceeds cap {max_bytes}")
                    tmp = dest.with_suffix(dest.suffix + ".part")
                    written = 0
                    with tmp.open("wb") as fh:
                        for chunk in resp.iter_bytes():
                            written += len(chunk)
                            if max_bytes and written > max_bytes:
                                tmp.unlink(missing_ok=True)
                                raise ValueError(f"download exceeded cap {max_bytes}")
                            fh.write(chunk)
                    tmp.replace(dest)
                    etag = resp.headers.get("ETag")
                    last_modified = resp.headers.get("Last-Modified")
                    digest = sha256_file(dest)
                    new_meta = {
                        "url": url,
                        "etag": etag,
                        "last_modified": last_modified,
                        "content_sha256": digest,
                        "bytes": dest.stat().st_size,
                        "fetched_at": utc_iso(),
                    }
                    write_meta(dest, new_meta)
                    log("http_fetched", url=url, bytes=new_meta["bytes"], dest=str(dest))
                    return CachedFetch(
                        path=dest,
                        status_code=resp.status_code,
                        not_modified=False,
                        etag=etag,
                        last_modified=last_modified,
                        content_sha256=digest,
                        bytes=new_meta["bytes"],
                        fetched_at=new_meta["fetched_at"],
                        from_cache=False,
                    )
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                log("http_retry", url=url, attempt=attempt + 1, error=str(exc))
                time.sleep(backoff**attempt)

        if dest.exists():
            log("http_last_good", url=url, dest=str(dest), error=str(last_error))
            return CachedFetch(
                path=dest,
                status_code=0,
                not_modified=True,
                etag=meta.get("etag"),
                last_modified=meta.get("last_modified"),
                content_sha256=meta.get("content_sha256") or sha256_file(dest),
                bytes=dest.stat().st_size,
                fetched_at=utc_iso(),
                from_cache=True,
            )
        if probe_name:
            probe = probe_fallback(self.settings, probe_name)
            if probe:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(probe.read_bytes())
                digest = sha256_file(dest)
                write_meta(
                    dest,
                    {
                        "url": url,
                        "etag": None,
                        "last_modified": None,
                        "content_sha256": digest,
                        "bytes": dest.stat().st_size,
                        "fetched_at": utc_iso(),
                        "from_probe": True,
                    },
                )
                log("http_probe_fallback", url=url, probe=str(probe))
                return CachedFetch(
                    path=dest,
                    status_code=0,
                    not_modified=True,
                    etag=None,
                    last_modified=None,
                    content_sha256=digest,
                    bytes=dest.stat().st_size,
                    fetched_at=utc_iso(),
                    from_cache=True,
                )
        raise last_error or RuntimeError(f"fetch failed: {url}")
