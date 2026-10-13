from thumbnail_service import ThumbnailRequest, generate_thumbnail


class RecordingTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, path, payload, request_id):
        self.calls.append((method, path, payload, request_id))
        if path.endswith("upload"):
            return {"ok": True, "data": {"id": "source-1"}, "error": None, "metadata": {}}
        return {"ok": True, "data": {"id": "thumb-1", "width": 640, "height": 360}, "error": None, "metadata": {}}


def test_release_requires_requested_dimensions():
    transport = RecordingTransport()
    result = generate_thumbnail(ThumbnailRequest("dashboard.png", "bytes"), transport)
    assert (result.width, result.height) == (640, 360)
    assert result.events == ["uploaded", "thumbnail_ready", "released"]
    assert transport.calls[1][0:2] == ("POST", "/v1/image/process")
    assert transport.calls[1][2]["ops"] == [
        {"op": "resize", "params": {"width": 640, "height": 360, "fit": "cover"}}
    ]
    assert set(transport.calls[1][2]) == {"image", "ops", "format", "store"}
    assert transport.calls[1][2]["image"] == {"image_id": "source-1"}
