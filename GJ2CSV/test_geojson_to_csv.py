import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

import geojson_to_csv as tool


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, features):
        path = self.root / name
        path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8-sig")
        return path

    def feature(self, properties, geometry=None):
        return {"type": "Feature", "properties": properties, "geometry": geometry}

    def run_tool(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return tool.main(list(args))

    def test_attributes_coordinates_and_csv_quoting(self):
        geometry = {"type": "Point", "coordinates": [139.5, 35.5, 12]}
        source = self.write("points.geojson", [self.feature({"name": '遺跡,「A」\n次の行', "lon": 130, "property_lon": "元", "list": ["縄文", "弥生"]}, geometry), self.feature({"later": "追加列"})])
        target = self.root / "points.csv"
        self.assertEqual(self.run_tool("-i", str(source), "-o", str(target)), 0)
        self.assertTrue(target.read_bytes().startswith(b"\xef\xbb\xbf"))
        with target.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["name"], '遺跡,「A」\n次の行')
        self.assertEqual(rows[0]["lon"], "139.5")
        self.assertEqual(rows[0]["property_property_lon"], "130")
        self.assertEqual(rows[0]["property_lon"], "元")
        self.assertEqual(json.loads(rows[0]["geometry_geojson"]), geometry)
        self.assertEqual(json.loads(rows[0]["list"]), ["縄文", "弥生"])
        self.assertEqual(rows[1]["later"], "追加列")
        self.assertEqual(rows[1]["lat"], "")

    def test_polygon_is_preserved_without_inventing_a_point(self):
        geometry = {"type": "Polygon", "coordinates": [[[139, 35], [140, 35], [140, 36], [139, 35]]]}
        source = self.write("polygon.geojson", [self.feature({"name": "範囲"}, geometry)])
        target = self.root / "polygon.csv"
        self.assertEqual(self.run_tool("-i", str(source), "-o", str(target)), 0)
        with target.open(encoding="utf-8-sig", newline="") as f:
            row = next(csv.DictReader(f))
        self.assertEqual(row["lon"], "")
        self.assertEqual(row["geometry_type"], "Polygon")
        self.assertEqual(json.loads(row["geometry_geojson"]), geometry)

    def test_existing_output_is_not_overwritten(self):
        source = self.write("source.geojson", [])
        target = self.root / "existing.csv"
        target.write_text("KEEP", encoding="utf-8")
        self.assertEqual(self.run_tool("-i", str(source), "-o", str(target)), 1)
        self.assertEqual(target.read_text(), "KEEP")
        self.assertEqual(self.run_tool("-i", str(source), "-o", str(target), "--overwrite"), 0)

    def test_invalid_batch_is_checked_before_output(self):
        folder = self.root / "input"
        folder.mkdir()
        self.write("valid.geojson", [self.feature({}, {"type": "Point", "coordinates": [139, 35]})]).rename(folder / "a.geojson")
        self.write("invalid.geojson", [self.feature({}, {"type": "Point", "coordinates": [139, 200]})]).rename(folder / "b.geojson")
        target = self.root / "output"
        self.assertEqual(self.run_tool("-i", str(folder), "-o", str(target)), 1)
        self.assertFalse(target.exists())

    def test_duplicate_output_stems_stop(self):
        folder = self.root / "input"
        folder.mkdir()
        for suffix in (".json", ".geojson"):
            self.write("same" + suffix, []).rename(folder / ("same" + suffix))
        self.assertEqual(self.run_tool("-i", str(folder), "-o", str(self.root / "out")), 1)

    def test_crs_and_nonfinite_values_are_rejected(self):
        with self.assertRaises(ValueError):
            tool.point_coordinates({"coordinates": [True, 35]}, "test")
        source = self.root / "nonfinite.geojson"
        source.write_text('{"type":"FeatureCollection","features":[],"bad":NaN}')
        with self.assertRaises(ValueError):
            tool.read_features(source)
        source.write_text('{"type":"FeatureCollection","features":[],"crs":{"properties":{"name":"EPSG:3857"}}}')
        with self.assertRaises(ValueError):
            tool.read_features(source)


if __name__ == "__main__":
    unittest.main()
