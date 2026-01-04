import importlib
import sys
import types
from pathlib import Path

import pytest


class FakeArray(list):
    """Minimal array-like object that supports the operations used in tests."""

    def astype(self, _dtype):
        return FakeArray([[float(value) for value in row] for row in self])

    def max(self):
        if not self:
            return 0
        return max(max(row) for row in self)

    def __itruediv__(self, value):
        for row_index, row in enumerate(self):
            self[row_index] = [val / value for val in row]
        return self


class FakeImagejRoi:
    POLYLINE = "polyline"

    def __init__(self, points, subtype=None):
        self.points = list(points)
        self.subtype = subtype

    @classmethod
    def frompoints(cls, points, subtype=None):
        return cls(points, subtype=subtype)

    @staticmethod
    def write_roi_zip(path, rois):
        import json
        import zipfile

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as zf:
            for idx, roi in enumerate(rois):
                zf.writestr(
                    f"roi_{idx}.json",
                    json.dumps({"points": roi.points, "subtype": roi.subtype}),
                )

    @staticmethod
    def read_roi_zip(path):
        import json
        import zipfile

        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                return json.loads(zf.read(name).decode())
        return None


@pytest.fixture(autouse=True)
def patch_image_stack(monkeypatch):
    """Provide lightweight stand-ins for numpy, skimage.io, and roifile."""

    fake_numpy = types.ModuleType("numpy")
    fake_numpy.float32 = float

    def fake_array(values):
        return FakeArray(values)

    fake_numpy.array = fake_array

    fake_io = types.ModuleType("skimage.io")

    def imread(_path):
        # Provide predictable pixel data for normalization and tracking.
        return FakeArray([[0, 2], [2, 4]])

    fake_io.imread = imread

    fake_skimage = types.ModuleType("skimage")
    fake_skimage.io = fake_io

    fake_roifile = types.ModuleType("roifile")
    fake_roifile.ImagejRoi = FakeImagejRoi

    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)
    monkeypatch.setitem(sys.modules, "skimage", fake_skimage)
    monkeypatch.setitem(sys.modules, "skimage.io", fake_io)
    monkeypatch.setitem(sys.modules, "roifile", fake_roifile)

    # Provide a baseline lumicks.pylake stub so imports succeed even without the
    # more detailed `fake_lumicks` fixture.
    base_pylake = types.ModuleType("lumicks.pylake")
    base_pylake.track_greedy = lambda *args, **kwargs: []
    base_lumicks = types.ModuleType("lumicks")
    base_lumicks.pylake = base_pylake
    monkeypatch.setitem(sys.modules, "lumicks", base_lumicks)
    monkeypatch.setitem(sys.modules, "lumicks.pylake", base_pylake)

    # Ensure modules that depend on these stubs are reloaded fresh in each test.
    for module_name in [
        "kymograph_processing.lumicks_tracker",
    ]:
        sys.modules.pop(module_name, None)

    yield

    for name in ["numpy", "skimage", "skimage.io", "roifile", "lumicks", "lumicks.pylake"]:
        sys.modules.pop(name, None)


@pytest.fixture
def fake_lumicks(monkeypatch):
    """Stub lumicks.pylake with a predictable greedy tracker."""

    track_calls = []

    def track_greedy(image, min_len=5, intensity_threshold=0.0):
        track_calls.append(
            {"image": image, "min_len": min_len, "intensity_threshold": intensity_threshold}
        )
        return [
            [(0, 0), (1, 1), (2, 1)],
            [(0, 1), (1, 2)],
        ]

    pylake_module = types.ModuleType("lumicks.pylake")
    pylake_module.track_greedy = track_greedy

    lumicks_module = types.ModuleType("lumicks")
    lumicks_module.pylake = pylake_module

    monkeypatch.setitem(sys.modules, "lumicks", lumicks_module)
    monkeypatch.setitem(sys.modules, "lumicks.pylake", pylake_module)

    yield track_calls

    for name in ["lumicks", "lumicks.pylake"]:
        sys.modules.pop(name, None)


@pytest.fixture
def sample_kymo_path(tmp_path_factory):
    """Create a tiny placeholder TIFF-like file for tests."""

    fixture_dir = tmp_path_factory.mktemp("fixtures")
    tif_path = fixture_dir / "sample_kymo.tif"
    tif_path.write_bytes(b"II*\x00FAKE_KYMO_DATA")
    return tif_path


@pytest.fixture
def sample_roi_zip(tmp_path_factory):
    """Create a minimal ROI ZIP archive for tests."""

    import json
    import zipfile

    fixture_dir = tmp_path_factory.mktemp("fixtures")
    roi_zip = fixture_dir / "sample_roi.zip"
    roi_content = {"points": [(0, 0), (1, 1), (2, 1)], "subtype": "polyline"}
    with zipfile.ZipFile(roi_zip, "w") as zf:
        zf.writestr("roi_0.json", json.dumps(roi_content))
    return roi_zip
