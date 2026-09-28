#!/usr/bin/env python3
"""Convert GSI Fundamental Geospatial Data DEM XML/ZIP files to a GeoTIFF mosaic."""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
import re
import shutil
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET
import zipfile


NAMESPACES = {
    "fgd": "http://fgd.gsi.go.jp/spec/2008/FGD_GMLSchema",
    "gml": "http://www.opengis.net/gml/3.2",
}
XML_NAME = re.compile(
    r"^FG-GML-(\d{4})-(\d{2})(?:-(\d{2}))?-(DEM(?:1A|5[ABC]|10[AB]))-(\d{8})\.xml$",
    re.IGNORECASE,
)
ZIP_NAME = re.compile(
    r"^FG-GML-(\d{4})-?(\d{2})-(DEM(?:1A|5[ABC]|10[AB]))(?:-(\d{8}))?\.zip$",
    re.IGNORECASE,
)
NODATA = -9999.0
SHAPES = {"1": (750, 1125), "5": (150, 225), "10": (750, 1125)}


class DemError(Exception):
    """Input or processing error to show without a traceback."""


@dataclass(frozen=True)
class Source:
    path: Path
    member: str | None
    name: str
    mesh: str
    kind: str
    date: str

    @property
    def label(self) -> str:
        return f"{self.path.name}:{self.member}" if self.member else self.path.name


@dataclass(frozen=True)
class TileInfo:
    source: Source
    rows: int
    cols: int
    start: int
    bounds: tuple[float, float, float, float]  # west, south, east, north
    datum: str


def mesh_size(kind: str) -> str:
    return kind[3:-1]


def parse_name(name: str) -> tuple[str, str, str]:
    match = XML_NAME.fullmatch(name)
    if not match:
        raise DemError(f"GMLファイル名が国土地理院DEMの形式ではありません: {name}")
    first, second, third, kind, date = match.groups()
    kind = kind.upper()
    size = mesh_size(kind)
    if (size == "10" and third is not None) or (size != "10" and third is None):
        raise DemError(f"メッシュ番号の桁数とDEMの格子間隔が一致しません: {name}")
    mesh = first + second + (third or "")
    mesh_position(mesh)  # digit ranges are part of the file-name check
    try:
        datetime.strptime(date, "%Y%m%d")
    except ValueError as exc:
        raise DemError(f"作成年月日が不正です: {name}") from exc
    return mesh, kind, date


def mesh_position(code: str) -> tuple[int, int]:
    if len(code) not in (6, 8) or not code.isdecimal():
        raise DemError(f"地域メッシュ番号が不正です: {code}")
    south, east = int(code[:2]), int(code[2:4])
    lat2, lon2 = int(code[4]), int(code[5])
    if not (0 <= lat2 < 8 and 0 <= lon2 < 8):
        raise DemError(f"2次メッシュ番号が不正です: {code}")
    row, col = south * 8 + lat2, east * 8 + lon2
    if len(code) == 8:
        row = row * 10 + int(code[6])
        col = col * 10 + int(code[7])
    return row, col


def mesh_bounds(code: str) -> tuple[float, float, float, float]:
    row, col = mesh_position(code)
    scale = 10 if len(code) == 8 else 1
    south = row / (12 * scale)
    west = 100 + col / (8 * scale)
    return west, south, west + 1 / (8 * scale), south + 1 / (12 * scale)


def sources_in(folder: Path) -> list[Source]:
    if not folder.is_dir():
        raise DemError(f"入力フォルダがありません: {folder}")
    sources: list[Source] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".xml", ".zip"):
            continue
        if path.suffix.lower() == ".xml":
            mesh, kind, date = parse_name(path.name)
            sources.append(Source(path, None, path.name, mesh, kind, date))
            continue
        match = ZIP_NAME.fullmatch(path.name)
        if not match:
            raise DemError(f"ZIPファイル名が国土地理院DEMの形式ではありません: {path.name}")
        first, second, archive_kind, archive_date = match.groups()
        archive_mesh = first + second
        mesh_position(archive_mesh)
        try:
            if archive_date:
                datetime.strptime(archive_date, "%Y%m%d")
            with zipfile.ZipFile(path) as archive:
                members = [item.filename for item in archive.infolist()
                           if not item.is_dir() and item.filename.lower().endswith(".xml")]
        except (OSError, zipfile.BadZipFile, ValueError) as exc:
            raise DemError(f"ZIPを読めません: {path.name}: {exc}") from exc
        if not members:
            raise DemError(f"ZIP内にDEMのXMLがありません: {path.name}")
        for member in members:
            name = Path(member).name
            mesh, kind, date = parse_name(name)
            if kind != archive_kind.upper() or mesh[:6] != archive_mesh:
                raise DemError(f"ZIP名と中のXMLのメッシュ番号・種類が一致しません: {path.name}: {name}")
            sources.append(Source(path, member, name, mesh, kind, date))
    if not sources:
        raise DemError(f"XMLまたはDEMのZIPが見つかりません: {folder}")
    return sources


def check_coverage(sources: list[Source], expected_file: Path | None) -> str:
    sizes = {mesh_size(item.kind) for item in sources}
    if len(sizes) != 1:
        raise DemError(f"異なる格子間隔のDEMが混在しています: {', '.join(sorted(sizes))}m")
    size = sizes.pop()
    by_mesh: dict[str, Source] = {}
    for item in sources:
        if item.mesh in by_mesh:
            raise DemError(f"地域メッシュが重複しています: {item.mesh} ({by_mesh[item.mesh].label}, {item.label})")
        by_mesh[item.mesh] = item

    points = {mesh_position(code) for code in by_mesh}
    seen = {next(iter(points))}
    pending = list(seen)
    while pending:
        row, col = pending.pop()
        for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            if neighbor in points and neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    if seen != points:
        raise DemError("地域メッシュが辺でつながっていません。離れた区画または途中の欠落を確認してください。")

    # A missing tile enclosed on all sides is a gap; irregular outside edges are valid.
    min_row = min(row for row, _ in points) - 1
    max_row = max(row for row, _ in points) + 1
    min_col = min(col for _, col in points) - 1
    max_col = max(col for _, col in points) + 1
    exterior = {(min_row, min_col)}
    pending = [(min_row, min_col)]
    while pending:
        row, col = pending.pop()
        for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            nr, nc = neighbor
            if (min_row <= nr <= max_row and min_col <= nc <= max_col
                    and neighbor not in points and neighbor not in exterior):
                exterior.add(neighbor)
                pending.append(neighbor)
    area = (max_row - min_row + 1) * (max_col - min_col + 1)
    if len(points) + len(exterior) != area:
        raise DemError("地域メッシュに囲まれた欠落があります。入力ファイルを確認してください。")

    if expected_file:
        try:
            expected = {line.strip() for line in expected_file.read_text(encoding="utf-8").splitlines()
                        if line.strip() and not line.lstrip().startswith("#")}
        except OSError as exc:
            raise DemError(f"予定メッシュ一覧を読めません: {expected_file}: {exc}") from exc
        if not expected:
            raise DemError("予定メッシュ一覧が空です。")
        for code in expected:
            if len(code) != len(next(iter(by_mesh))):
                raise DemError(f"予定メッシュ番号の桁数が入力と異なります: {code}")
            mesh_position(code)
        missing, extra = expected - by_mesh.keys(), by_mesh.keys() - expected
        if missing or extra:
            raise DemError(f"予定メッシュと一致しません。欠落: {', '.join(sorted(missing)) or 'なし'} / "
                           f"一覧外: {', '.join(sorted(extra)) or 'なし'}")
    return size


@contextmanager
def open_source(source: Source):
    if source.member is None:
        with source.path.open("rb") as stream:
            yield stream
    else:
        with zipfile.ZipFile(source.path) as archive, archive.open(source.member) as stream:
            yield stream


def child(parent: ET.Element, query: str, source: Source) -> ET.Element:
    result = parent.find(query, NAMESPACES)
    if result is None:
        raise DemError(f"DEMの必須項目がありません ({query}): {source.label}")
    return result


def parse_tile(source: Source, include_values: bool = False):
    try:
        with open_source(source) as stream:
            root = ET.parse(stream).getroot()
    except (ET.ParseError, OSError, zipfile.BadZipFile) as exc:
        raise DemError(f"GMLを読めません: {source.label}: {exc}") from exc
    dem = child(root, ".//fgd:DEM", source)
    mesh = child(dem, "fgd:mesh", source).text
    if mesh is None or mesh.strip() != source.mesh:
        raise DemError(f"ファイル名とGML内のメッシュ番号が異なります: {source.label}")
    coverage = child(dem, "fgd:coverage", source)
    envelope = child(coverage, ".//gml:Envelope", source)
    srs = envelope.get("srsName", "").lower()
    if "jgd2024" in srs:
        datum = "JGD2024"
    elif "jgd2011" in srs:
        datum = "JGD2011"
    else:
        raise DemError(f"JGD2011/JGD2024以外の座標参照系です: {source.label}: {srs or '(なし)'}")
    try:
        lower = tuple(map(float, child(envelope, "gml:lowerCorner", source).text.split()))
        upper = tuple(map(float, child(envelope, "gml:upperCorner", source).text.split()))
        low = tuple(map(int, child(coverage, ".//gml:Grid/gml:limits/gml:GridEnvelope/gml:low", source).text.split()))
        high = tuple(map(int, child(coverage, ".//gml:Grid/gml:limits/gml:GridEnvelope/gml:high", source).text.split()))
        start_element = coverage.find(".//gml:GridFunction/gml:startPoint", NAMESPACES)
        sx, sy = map(int, start_element.text.split()) if start_element is not None else (0, 0)
    except (TypeError, ValueError, AttributeError) as exc:
        raise DemError(f"GMLの座標・格子情報が不正です: {source.label}") from exc
    size = mesh_size(source.kind)
    rows, cols = SHAPES[size]
    if low != (0, 0) or high != (cols - 1, rows - 1) or not (0 <= sx < cols and 0 <= sy < rows):
        raise DemError(f"GMLの格子数または開始位置がDEM{size}の仕様と異なります: {source.label}")
    bounds = mesh_bounds(source.mesh)
    west, south, east, north = bounds
    if (len(lower) != 2 or len(upper) != 2
            or any(abs(a - b) > 1e-6 for a, b in zip(lower, (south, west)))
            or any(abs(a - b) > 1e-6 for a, b in zip(upper, (north, east)))):
        raise DemError(f"GMLの範囲とファイル名の地域メッシュが一致しません: {source.label}")
    info = TileInfo(source, rows, cols, sy * cols + sx, bounds, datum)
    if not include_values:
        return info

    import numpy as np

    tuple_list = child(coverage, ".//gml:DataBlock/gml:tupleList", source).text
    if not tuple_list:
        raise DemError(f"標高値がありません: {source.label}")
    data = np.full(rows * cols, NODATA, dtype="float32")
    index = info.start
    count = 0
    for line in StringIO(tuple_list):
        line = line.strip()
        if not line:
            continue
        category, sep, value = line.partition(",")
        if not sep or not category.strip():
            raise DemError(f"標高値の記述が不正です: {source.label}: {line[:80]}")
        if index >= data.size:
            raise DemError(f"標高値が格子数を超えています: {source.label}")
        try:
            data[index] = float(value)
        except ValueError as exc:
            raise DemError(f"標高値を数値にできません: {source.label}: {value[:80]}") from exc
        if not np.isfinite(data[index]):
            raise DemError(f"標高値が有限の数値ではありません: {source.label}")
        index += 1
        count += 1
    if not count:
        raise DemError(f"標高値がありません: {source.label}")
    return info, data.reshape(rows, cols)


def convert_and_merge(sources: list[Source], output: Path, infos: list[TileInfo]) -> Path:
    import rasterio
    from rasterio.merge import merge
    from rasterio.transform import from_bounds

    if output.exists() and not output.is_dir():
        raise DemError(f"出力先がフォルダではありません: {output}")
    if (output / "tiles").exists() or (output / "dem_merged.tif").exists():
        raise DemError(f"出力が既にあります。退避または削除して再実行してください: {output}")
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="dem-merge-", dir=output) as temp_name:
        temp = Path(temp_name)
        tile_dir = temp / "tiles"
        tile_dir.mkdir()
        tile_paths = []
        datum = infos[0].datum
        for source in sources:
            info, values = parse_tile(source, include_values=True)
            tile_path = tile_dir / f"{source.name[:-4]}.tif"
            with rasterio.open(
                tile_path, "w", driver="GTiff", width=info.cols, height=info.rows,
                count=1, dtype="float32", crs="EPSG:6668",
                transform=from_bounds(*info.bounds, info.cols, info.rows),
                nodata=NODATA, compress="deflate", tiled=True, BIGTIFF="IF_SAFER",
            ) as dst:
                dst.write(values, 1)
                dst.update_tags(GSI_VERTICAL_DATUM=datum, SOURCE_MESH=source.mesh,
                                SOURCE_FILE=source.name)
            tile_paths.append(tile_path)
            print(f"変換: {source.label} → {tile_path.name}")
        merged = temp / "dem_merged.tif"
        with ExitStack() as stack:
            readers = [stack.enter_context(rasterio.open(path)) for path in tile_paths]
            merge(readers, dst_path=merged, nodata=NODATA, dtype="float32", mem_limit=64,
                  dst_kwds={"compress": "deflate", "tiled": True, "BIGTIFF": "IF_SAFER"})
        with rasterio.open(merged, "r+") as dst:
            dst.update_tags(GSI_VERTICAL_DATUM=datum, SOURCE="GSI Fundamental Geospatial Data DEM")
        shutil.move(str(tile_dir), str(output / "tiles"))
        shutil.move(str(merged), str(output / "dem_merged.tif"))
    return output / "dem_merged.tif"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="国土地理院DEMのGMLをGeoTIFFに変換・結合します。")
    parser.add_argument("--input", type=Path, default=Path.cwd() / "inputGML",
                        help="XML/ZIPの入力フォルダ（既定: 作業中の場所/inputGML）")
    parser.add_argument("--output", type=Path, default=Path.cwd() / "output",
                        help="出力フォルダ（既定: 作業中の場所/output）")
    parser.add_argument("--expected-meshes", type=Path,
                        help="必要な地域メッシュ番号を1行1件で記したテキストファイル")
    args = parser.parse_args(argv)
    try:
        sources = sources_in(args.input)
        size = check_coverage(sources, args.expected_meshes)
        infos = [parse_tile(source) for source in sources]
        datums = {info.datum for info in infos}
        if len(datums) != 1:
            raise DemError("JGD2011とJGD2024の標高が混在しています。別々に処理してください。")
        print(f"確認済み: DEM{size}m、{len(sources)}ファイル、{next(iter(datums))}")
        result = convert_and_merge(sources, args.output, infos)
        print(f"完了: {result}")
        return 0
    except (DemError, OSError, ImportError, ValueError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
