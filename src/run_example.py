from __future__ import annotations

import uuid
import base64
import struct
import zlib

from thumbnail_service import InfraiError, InfraiTransport, ThumbnailRequest, generate_thumbnail


def sample_png():
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))

    pixels = (b"\x00" + b"\x20\x80\xc0" * 16) * 16
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", 16, 16, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


class CleaningTransport:
    def __init__(self):
        self.transport = InfraiTransport()
        self.source_id = None

    def request(self, method, path, payload, request_id):
        response = self.transport.request(method, path, payload, request_id)
        if path == "/v1/image/upload":
            self.source_id = (response["data"].get("image_id") or response["data"].get("id")
                              or response["data"].get("image"))
        return response


if __name__ == "__main__":
    transport = CleaningTransport()
    try:
        result = generate_thumbnail(ThumbnailRequest("dashboard.png", sample_png()), transport)
        print(f"released {result.thumbnail_id} at {result.width}x{result.height}: {', '.join(result.events)}")
    finally:
        if transport.source_id:
            transport.request("DELETE", f"/v1/image/delete/{transport.source_id}", {}, str(uuid.uuid4()))
            try:
                transport.request("GET", f"/v1/image/get/{transport.source_id}", {}, str(uuid.uuid4()))
            except InfraiError as exc:
                if exc.status != 404:
                    raise
            else:
                raise RuntimeError("uploaded sample still exists after deletion")
