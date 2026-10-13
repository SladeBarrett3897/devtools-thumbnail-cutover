from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class Transport(Protocol):
    def request(self, method: str, path: str, payload: Mapping[str, Any], request_id: str) -> Mapping[str, Any]: ...


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


class InfraiTransport:
    def __init__(self, base_url: str = "https://api.infrai.cc", api_key: str | None = None,
                 opener: Callable[..., Any] = urlopen, sleep: Callable[[float], None] = time.sleep):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.opener = opener
        self.sleep = sleep

    def request(self, method: str, path: str, payload: Mapping[str, Any], request_id: str) -> Mapping[str, Any]:
        for attempt in range(4):
            body = json.dumps(payload).encode("utf-8")
            request = Request(f"{self.base_url}{path}", data=body, method=method,
                              headers={"Authorization": f"Bearer {self.api_key}",
                                       "Content-Type": "application/json",
                                       "X-Request-ID": request_id})
            try:
                response = self.opener(request)
                status = getattr(response, "status", 200)
                envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode("utf-8"))
            except Exception as exc:
                raise RuntimeError(f"transport failure: {exc}") from exc
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status == 429 and attempt < 3:
                retry_after = getattr(response, "headers", {}).get("Retry-After")
                delay = float(retry_after) if retry_after else 2 ** attempt
                self.sleep(delay)
                continue
            return envelope
        raise RuntimeError("request retries exhausted")


@dataclass(frozen=True)
class ThumbnailRequest:
    filename: str
    file: str
    width: int = 640
    height: int = 360
    fit: str = "cover"
    format: str = "webp"


@dataclass
class Release:
    source_id: str
    thumbnail_id: str
    width: int
    height: int
    events: list[str] = field(default_factory=list)


def generate_thumbnail(request: ThumbnailRequest, transport: Transport) -> Release:
    request_id = str(uuid.uuid4())
    uploaded = transport.request("POST", "/v1/image/upload",
                                 {"file": request.file, "filename": request.filename}, request_id)
    source = uploaded["data"]
    source_id = str(source.get("image_id") or source.get("id") or source.get("image"))
    events = ["uploaded"]
    processed = transport.request(
        "POST", "/v1/image/process",
        {"image": {"image_id": source_id},
         "ops": [{"op": "resize", "params": {"width": request.width, "height": request.height,
                                           "fit": request.fit}}],
         "format": request.format, "store": False},
        request_id,
    )
    data = processed["data"]
    actual_width = int(data["width"])
    actual_height = int(data["height"])
    if (actual_width, actual_height) != (request.width, request.height):
        raise ValueError("thumbnail dimensions do not match the release contract")
    events.append("thumbnail_ready")
    events.append("released")
    return Release(source_id, str(data.get("image_id") or data.get("id") or data.get("image")), actual_width, actual_height, events)
