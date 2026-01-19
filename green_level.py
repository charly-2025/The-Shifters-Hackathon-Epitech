#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from typing import Iterable, Optional, Tuple, List

import requests
from shapely.geometry import shape, Polygon, MultiPolygon, LinearRing, box
from shapely.ops import transform
from shapely.validation import make_valid
from pyproj import Transformer

GEO_API = "https://geo.api.gouv.fr"
OVERPASS_URL_DEFAULT = "https://overpass-api.de/api/interpreter"

GREEN_FILTERS: List[Tuple[str, str]] = [
    ("leisure", "park"),
    ("landuse", "forest"),
    ("landuse", "grass"),
    ("landuse", "meadow"),
    ("natural", "wood"),
    ("natural", "grassland"),
]


def fetch_commune_contour_geom(insee: str, timeout: int = 30):
    """
    Force a polygon by requesting GeoJSON with geometry=contour.
    """
    url = f"{GEO_API}/communes/{insee}?format=geojson&geometry=contour"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    gj = r.json()
    geom = shape(gj["geometry"])
    return geom


def ensure_polygon_like(geom):
    """
    Ensure we have a Polygon/MultiPolygon.
    If not, fallback to bbox (last resort, less precise).
    """
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom

    # bbox fallback
    minx, miny, maxx, maxy = geom.bounds
    return box(minx, miny, maxx, maxy)


def wgs84_area_km2(geom) -> float:
    to_l93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    geom_l93 = transform(to_l93.transform, geom)
    return geom_l93.area / 1e6


def polygon_to_overpass_poly(geom, simplify_tolerance_deg: float) -> str:
    if isinstance(geom, MultiPolygon):
        geom = max(list(geom.geoms), key=lambda g: g.area)
    if not isinstance(geom, Polygon):
        raise TypeError(f"Expected Polygon, got {geom.geom_type}")

    g = geom
    if simplify_tolerance_deg and simplify_tolerance_deg > 0:
        g = geom.simplify(simplify_tolerance_deg, preserve_topology=True)

    coords = list(g.exterior.coords)
    return " ".join([f"{lat:.6f} {lon:.6f}" for lon, lat in coords])


def build_overpass_query(poly_str: str, timeout_s: int) -> str:
    parts = []
    for k, v in GREEN_FILTERS:
        parts.append(f'way["{k}"="{v}"](poly:"{poly_str}");')
        parts.append(f'relation["{k}"="{v}"](poly:"{poly_str}");')
    body = "\n  ".join(parts)
    return f"""
[out:json][timeout:{timeout_s}];
(
  {body}
);
out geom;
""".strip()


def overpass_request(overpass_url: str, query: str, timeout: int = 2400000000) -> dict:
    r = requests.post(overpass_url, data={"data": query}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def element_to_polygon(el) -> Optional[Polygon]:
    geom = el.get("geometry")
    if not geom or len(geom) < 4:
        return None

    coords = [(p["lon"], p["lat"]) for p in geom]
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    try:
        ring = LinearRing(coords)
        if not ring.is_valid:
            return None
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = make_valid(poly)

        if poly.geom_type == "Polygon":
            return poly
        if poly.geom_type == "MultiPolygon":
            return max(list(poly.geoms), key=lambda g: g.area)
        return None
    except Exception:
        return None


def union_area_km2(geoms: Iterable[Polygon]) -> float:
    geoms = list(geoms)
    if not geoms:
        return 0.0
    u = geoms[0]
    for g in geoms[1:]:
        u = u.union(g)
    return wgs84_area_km2(u)


def main() -> int:
    p = argparse.ArgumentParser(description="Compute green level for a commune (INSEE code).")
    p.add_argument("--insee", default="35238", help="INSEE commune code (default: 35238 Rennes)")
    p.add_argument("--population", type=int, default=0, help="Population for m²/person (optional)")
    p.add_argument("--simplify", type=float, default=0.0003,
                   help="Boundary simplification tolerance in degrees (higher=faster, less precise)")
    p.add_argument("--overpass", default=OVERPASS_URL_DEFAULT, help="Overpass API endpoint")
    p.add_argument("--timeout", type=int, default=180, help="Overpass query timeout (seconds)")
    args = p.parse_args()

    insee = args.insee.strip()

    try:
        geom_raw = fetch_commune_contour_geom(insee)
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch commune contour for INSEE {insee}: {e}", file=sys.stderr)
        return 2

    commune_geom = ensure_polygon_like(geom_raw)
    if commune_geom.geom_type != "Polygon" and commune_geom.geom_type != "MultiPolygon":
        print(f"[WARN] Unexpected geometry ({geom_raw.geom_type}); using bbox fallback (less precise).", file=sys.stderr)

    commune_area = wgs84_area_km2(commune_geom)

    # Overpass needs a Polygon ring; take largest polygon if multipolygon
    if isinstance(commune_geom, MultiPolygon):
        poly_geom = max(list(commune_geom.geoms), key=lambda g: g.area)
    else:
        poly_geom = commune_geom

    poly_str = polygon_to_overpass_poly(poly_geom, simplify_tolerance_deg=args.simplify)
    query = build_overpass_query(poly_str, timeout_s=args.timeout)

    try:
        osm = overpass_request(args.overpass, query)
    except requests.RequestException as e:
        print(f"[ERROR] Overpass request failed: {e}", file=sys.stderr)
        print("Tip: increase --simplify (e.g. 0.001) or try another --overpass endpoint.", file=sys.stderr)
        return 3

    greens: List[Polygon] = []
    for el in osm.get("elements", []):
        poly_el = element_to_polygon(el)
        if poly_el is None:
            continue
        clipped = poly_el.intersection(commune_geom)
        if clipped.is_empty:
            continue
        if clipped.geom_type == "Polygon":
            greens.append(clipped)
        elif clipped.geom_type == "MultiPolygon":
            greens.extend(list(clipped.geoms))

    green_area = union_area_km2(greens)
    share_pct = (100.0 * green_area / commune_area) if commune_area else 0.0

    print(f"INSEE: {insee}")
    print(f"Commune area: {commune_area:.2f} km²")
    print(f"Green area:   {green_area:.2f} km²")
    print(f"Green share:  {share_pct:.1f}%")

    if args.population and args.population > 0:
        m2_per_person = (green_area * 1e6) / args.population
        print(f"Green per capita: {m2_per_person:.1f} m²/person (population={args.population})")

    score = max(0.0, min(100.0, 100.0 * (share_pct / 60.0)))  # 60%+ => 100
    print(f"Green level score: {score:.1f} / 100 (heuristic; calibrate across cities)")
    return 0


if __name__ == "__main__":
     main()



