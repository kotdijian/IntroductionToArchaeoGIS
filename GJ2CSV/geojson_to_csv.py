#!/usr/bin/env python3
"""Convert GeoJSON features to Excel-friendly CSV using only Python's standard library."""

import argparse
import csv
import json
import math
import os
import sys
import tempfile
from pathlib import Path

RESERVED = ("lon", "lat", "geometry_type", "geometry_geojson", "feature_id")
GEOMETRIES = {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon", "GeometryCollection"}


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list, bool)):
        return compact(value)
    return value


def reject_constant(value):
    raise ValueError(f"JSONに使用できない数値です: {value}")


def point_coordinates(geometry, where):
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValueError(f"{where}: Pointの座標には経度・緯度が必要です。")
    if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in coordinates):
        raise ValueError(f"{where}: 座標は有限の数値で指定してください。")
    lon, lat = coordinates[:2]
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError(f"{where}: 経度・緯度の範囲が不正です。CRSを確認してください。")
    return lon, lat


def validate_geometry(geometry, where):
    if geometry is None:
        return
    if not isinstance(geometry, dict) or geometry.get("type") not in GEOMETRIES:
        raise ValueError(f"{where}: GeoJSONの図形の種類が不正です。")
    if geometry["type"] == "Point":
        point_coordinates(geometry, where)
    elif geometry["type"] == "GeometryCollection":
        parts = geometry.get("geometries")
        if not isinstance(parts, list):
            raise ValueError(f"{where}: geometriesは配列で指定してください。")
        for part in parts:
            if part is None:
                raise ValueError(f"{where}: GeometryCollection内の図形が空です。")
            validate_geometry(part, where)
    elif not isinstance(geometry.get("coordinates"), list):
        raise ValueError(f"{where}: coordinatesは配列で指定してください。")


def read_features(path):
    with path.open(encoding="utf-8-sig") as stream:
        data = json.load(stream, parse_constant=reject_constant)
    if not isinstance(data, dict):
        raise ValueError("GeoJSONの最上位はオブジェクトである必要があります。")
    crs = data.get("crs")
    if crs is not None:
        name = crs.get("properties", {}).get("name", "") if isinstance(crs, dict) else ""
        if name not in {"EPSG:4326", "urn:ogc:def:crs:EPSG::4326", "urn:ogc:def:crs:OGC:1.3:CRS84", "OGC:CRS84"}:
            raise ValueError("WGS 84以外または不明なCRSです。QGIS等でEPSG:4326のGeoJSONへ変換してください。")
    if data.get("type") == "FeatureCollection":
        features = data.get("features")
    elif data.get("type") == "Feature":
        features = [data]
    else:
        raise ValueError("FeatureCollectionまたはFeature形式のGeoJSONを指定してください。")
    if not isinstance(features, list):
        raise ValueError("featuresは配列で指定してください。")
    keys = []
    for number, feature in enumerate(features, 1):
        where = f"地物{number}"
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError(f"{where}: Feature形式ではありません。")
        if "geometry" not in feature or "properties" not in feature:
            raise ValueError(f"{where}: geometryとpropertiesが必要です。")
        properties = feature["properties"]
        if properties is not None and not isinstance(properties, dict):
            raise ValueError(f"{where}: propertiesはオブジェクトまたはnullで指定してください。")
        for key in properties or {}:
            if key not in keys:
                keys.append(key)
        validate_geometry(feature["geometry"], where)
        # Reject non-finite numbers even when nested in attributes or non-point geometry.
        compact(feature)
    return features, keys


def csv_rows(features, keys):
    # Keep every original property; rename only collisions with generated columns.
    used = set(keys) | set(RESERVED)
    names = {}
    for key in keys:
        name = key
        if key in RESERVED:
            name = f"property_{key}"
            while name in used:
                name = "property_" + name
        names[key] = name
        used.add(name)
    fields = [names[key] for key in keys] + list(RESERVED)
    rows = []
    nonpoints = 0
    for feature in features:
        properties = feature["properties"] or {}
        row = {names[key]: cell(properties.get(key)) for key in keys}
        geometry = feature["geometry"]
        row.update(lon="", lat="", geometry_type="", geometry_geojson="", feature_id=cell(feature.get("id")))
        if geometry is not None:
            row["geometry_type"] = geometry["type"]
            row["geometry_geojson"] = compact(geometry)
            if geometry["type"] == "Point":
                row["lon"], row["lat"] = point_coordinates(geometry, "Point")
            else:
                nonpoints += 1
        rows.append(row)
    return fields, rows, {k: v for k, v in names.items() if k != v}, nonpoints


def convert(input_path, output_path, overwrite=False):
    features, keys = read_features(input_path)
    fields, rows, renamed, nonpoints = csv_rows(features, keys)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=output_path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        if overwrite:
            os.replace(temporary, output_path)
        else:
            # Exclusive destination creation prevents accidentally replacing an existing CSV.
            with output_path.open("xb") as target, temporary.open("rb") as source:
                import shutil
                shutil.copyfileobj(source, target)
        print(f"保存: {output_path}（{len(rows)}行）")
        if renamed:
            print("属性列の名前変更: " + ", ".join(f"{key} → {value}" for key, value in renamed.items()))
        if nonpoints:
            print(f"注意: Point以外の{nonpoints}件はlon・latを空欄とし、図形をgeometry_geojson列に保存しました。")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="地理院地図等のGeoJSONをCSVへ変換します。元データは変更しません。")
    parser.add_argument("-i", "--input", type=Path, default=Path("inputGeoJSON"), help="入力ファイルまたはフォルダ（既定: 現在の場所のinputGeoJSON）")
    parser.add_argument("-o", "--output", type=Path, default=Path("output"), help="出力フォルダ、または単一入力時の.csvファイル（既定: output）")
    parser.add_argument("--overwrite", action="store_true", help="既存のCSVを上書きする（指定しない場合は停止）")
    args = parser.parse_args(argv)
    try:
        if args.input.is_file():
            inputs = [args.input]
        elif args.input.is_dir():
            inputs = sorted(p for p in args.input.iterdir() if p.is_file() and p.suffix.lower() in {".geojson", ".json"})
        else:
            raise ValueError(f"入力が見つかりません: {args.input}")
        if not inputs:
            raise ValueError("入力フォルダに.geojsonまたは.jsonファイルがありません。")
        if args.output.suffix.lower() == ".csv":
            if len(inputs) != 1:
                raise ValueError("複数ファイルの変換では、出力フォルダを指定してください。")
            outputs = [args.output]
        else:
            outputs = [args.output / (p.stem + ".csv") for p in inputs]
        if len({str(p.resolve()).casefold() for p in outputs}) != len(outputs):
            raise ValueError("同じ出力名になる入力ファイルがあります。入力の名前を変えてください。")
        for source, target in zip(inputs, outputs):
            if source.resolve() == target.resolve():
                raise ValueError("入力と出力に同じファイルを指定できません。")
            if target.exists() and not args.overwrite:
                raise ValueError(f"出力が既にあります: {target}。別の保存先を指定するか、必要な結果を退避してください。")
            try:
                read_features(source)
            except (ValueError, UnicodeError) as error:
                raise ValueError(f"{source}: {error}") from error
        for source, target in zip(inputs, outputs):
            convert(source, target, args.overwrite)
    except (ValueError, OSError, OverflowError, RecursionError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
