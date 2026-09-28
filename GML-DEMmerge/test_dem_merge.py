"""Small synthetic GSI-style samples to check mosaics and failure gates."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
import zipfile

import dem_merge as app


def xml_for(mesh: str, kind: str, values: list[float], datum: str = "jgd2024",
            start: tuple[int, int] = (0, 0)) -> str:
    west, south, east, north = app.mesh_bounds(mesh)
    rows, cols = app.SHAPES[app.mesh_size(kind)]
    tuples = "\n".join(f"地表面,{value}" for value in values)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<fgd:Dataset xmlns:fgd="{app.NAMESPACES['fgd']}" xmlns:gml="{app.NAMESPACES['gml']}">
  <fgd:DEM><fgd:mesh>{mesh}</fgd:mesh><fgd:coverage>
    <gml:boundedBy><gml:Envelope srsName="fguuid:{datum}.bl">
      <gml:lowerCorner>{south:.12f} {west:.12f}</gml:lowerCorner>
      <gml:upperCorner>{north:.12f} {east:.12f}</gml:upperCorner>
    </gml:Envelope></gml:boundedBy>
    <gml:gridDomain><gml:Grid><gml:limits><gml:GridEnvelope>
      <gml:low>0 0</gml:low><gml:high>{cols - 1} {rows - 1}</gml:high>
    </gml:GridEnvelope></gml:limits></gml:Grid></gml:gridDomain>
    <gml:coverageFunction><gml:GridFunction><gml:startPoint>{start[0]} {start[1]}</gml:startPoint>
    </gml:GridFunction></gml:coverageFunction>
    <gml:rangeSet><gml:DataBlock><gml:tupleList>{tuples}</gml:tupleList>
    </gml:DataBlock></gml:rangeSet>
  </fgd:coverage></fgd:DEM>
</fgd:Dataset>"""


def add_xml(folder: Path, mesh: str, kind: str, values: list[float], datum="jgd2024",
            start=(0, 0)) -> Path:
    short = f"{mesh[:4]}-{mesh[4:6]}"
    if len(mesh) == 8:
        short += f"-{mesh[6:]}"
    file = folder / f"FG-GML-{short}-{kind}-20260901.xml"
    file.write_text(xml_for(mesh, kind, values, datum, start), encoding="utf-8")
    return file


class DemMergeTest(unittest.TestCase):
    def test_two_third_meshes_in_one_five_meter_zip(self):
        import rasterio

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "inputGML"
            input_dir.mkdir()
            first = add_xml(input_dir, "53395200", "DEM5A", [9.5], start=(2, 1))
            second = add_xml(input_dir, "53395201", "DEM5A", [17.25])
            with zipfile.ZipFile(input_dir / "FG-GML-533952-DEM5A-20260901.zip", "w") as z:
                for path in (first, second):
                    z.write(path, path.name)
                    path.unlink()
            with redirect_stdout(StringIO()):
                self.assertEqual(app.main(["--input", str(input_dir), "--output", str(root / "output")]), 0)
            with rasterio.open(root / "output" / "dem_merged.tif") as dataset:
                self.assertEqual((dataset.width, dataset.height), (450, 150))
                self.assertEqual(float(dataset.read(1, window=((1, 2), (2, 3)))[0, 0]), 9.5)
                self.assertEqual(float(dataset.read(1, window=((0, 1), (225, 226)))[0, 0]), 17.25)

    def test_adjacent_zip_and_xml_merge_correctly(self):
        import rasterio

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "inputGML"
            input_dir.mkdir()
            add_xml(input_dir, "533952", "DEM10B", [12.5, 13.75])
            next_xml = add_xml(input_dir, "533953", "DEM10B", [42.0])
            with zipfile.ZipFile(input_dir / "FG-GML-533953-DEM10B-20260901.zip", "w") as z:
                z.write(next_xml, next_xml.name)
            next_xml.unlink()
            with redirect_stdout(StringIO()):
                code = app.main(["--input", str(input_dir), "--output", str(root / "output")])
            self.assertEqual(code, 0)
            with rasterio.open(root / "output" / "dem_merged.tif") as dataset:
                self.assertEqual((dataset.width, dataset.height), (2250, 750))
                self.assertEqual(dataset.crs.to_epsg(), 6668)
                self.assertEqual(dataset.nodata, -9999)
                self.assertEqual(dataset.tags()["GSI_VERTICAL_DATUM"], "JGD2024")
                self.assertEqual(float(dataset.read(1, window=((0, 1), (0, 1)))[0, 0]), 12.5)
                self.assertEqual(float(dataset.read(1, window=((0, 1), (1125, 1126)))[0, 0]), 42.0)
                self.assertEqual(float(dataset.read(1, window=((1, 2), (0, 1)))[0, 0]), -9999)
            self.assertEqual(len(list((root / "output" / "tiles").glob("*.tif"))), 2)

    def test_disconnected_or_enclosed_gap_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            add_xml(folder, "533952", "DEM10B", [1])
            add_xml(folder, "533954", "DEM10B", [1])
            with self.assertRaisesRegex(app.DemError, "つながって"):
                app.check_coverage(app.sources_in(folder), None)
            (folder / "FG-GML-5339-54-DEM10B-20260901.xml").unlink()
            for code in ("533950", "533951", "533953", "533960", "533962", "533971", "533972", "533973"):
                add_xml(folder, code, "DEM10B", [1])
            # 533961 is enclosed by this ring, even though all other tiles connect.
            with self.assertRaisesRegex(app.DemError, "囲まれた欠落"):
                app.check_coverage(app.sources_in(folder), None)

    def test_mixed_resolution_and_expected_edge_tile_stops_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "inputGML"
            folder.mkdir()
            add_xml(folder, "533952", "DEM10B", [1])
            add_xml(folder, "53395200", "DEM5A", [1])
            output = root / "output"
            with redirect_stderr(StringIO()) as errors:
                self.assertEqual(app.main(["--input", str(folder), "--output", str(output)]), 1)
            self.assertIn("異なる格子間隔", errors.getvalue())
            self.assertFalse(output.exists())
            (folder / "FG-GML-5339-52-00-DEM5A-20260901.xml").unlink()
            expected = root / "expected.txt"
            expected.write_text("533952\n533953\n", encoding="utf-8")
            with redirect_stderr(StringIO()) as errors:
                self.assertEqual(app.main(["--input", str(folder), "--output", str(output),
                                           "--expected-meshes", str(expected)]), 1)
            self.assertIn("533953", errors.getvalue())
            self.assertFalse(output.exists())

    def test_datum_mismatch_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "inputGML"
            folder.mkdir()
            add_xml(folder, "533952", "DEM10B", [1], "jgd2024")
            add_xml(folder, "533953", "DEM10B", [1], "jgd2011")
            with redirect_stderr(StringIO()) as errors:
                self.assertEqual(app.main(["--input", str(folder), "--output", str(root / "output")]), 1)
            self.assertIn("JGD2011とJGD2024", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
