#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apicall.py — merged utility: ecological profile + green level + (optional) mobility.
Usage:
  python3 apicall.py "Rennes"
Optional:
  OPENAQ_API_KEY=... python3 apicall.py "Rennes"
  python3 apicall.py "Rennes" --year 2024 --no-green --no-mobility
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from typing import Any, Dict, Optional, List, Tuple

import requests

import os

api_key = os.getenv("***REMOVED***")
UTC = dt.timezone.utc
GEO_API = "https://geo.api.gouv.fr"

# ---------------------------
# HTTP helper (robust JSON + retry)
# ---------------------------

def _get_json(
    url: str,
    params: dict | None = None,
    read_timeout: int = 30,
    retries: int = 2,
    backoff: float = 1.6,
    allow_redirects: bool = True,
    headers: dict | None = None,
) -> dict:
    """
    Robust GET->JSON:
    - retries on timeouts + non-JSON
    - optional redirects (default True; needed for many APIs)
    """
    import json as _json

    h = {
        "User-Agent": "apicall.py/1.0",
        "Accept": "application/json,text/plain,*/*",
    }
    if headers:
        h.update(headers)

    last_exc: Exception | None = None
    last_text: str | None = None
    last_loc: str | None = None

    for i in range(retries):
        try:
            r = requests.get(
                url,
                params=params,
                headers=h,
                timeout=(10, read_timeout),
                allow_redirects=allow_redirects,
            )
            # If redirects are disabled, surface redirect target cleanly
            if not allow_redirects and 300 <= r.status_code < 400:
                last_loc = r.headers.get("Location")
                raise RuntimeError(f"Redirect {r.status_code} to {last_loc}")

            r.raise_for_status()

            text = r.text
            last_text = text[:300]
            ct = (r.headers.get("Content-Type") or "").lower()

            if "application/json" in ct or text.lstrip().startswith("{") or text.lstrip().startswith("["):
                return r.json()

            # sometimes ct is wrong; try parse anyway
            return _json.loads(text)

        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout) as e:
            last_exc = e
            time.sleep(backoff ** i)
        except Exception as e:
            last_exc = e
            time.sleep(backoff ** i)

    raise RuntimeError(
        f"Failed to fetch JSON from {url}. Last error: {type(last_exc).__name__}: {last_exc}. "
        f"Last redirect location: {last_loc!r}. Last body head: {last_text!r}"
    )


def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC)


def _try_int(x) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return None


def _try_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


# ---------------------------
# Geo: city name -> INSEE + basic meta
# ---------------------------

def resolve_city_to_insee(city_name: str) -> dict:
    """
    Resolve a city name (French commune) to an INSEE code using geo.api.gouv.fr.
    Returns {ok, insee, nom, ...} or {ok:false, error}
    """
    q = city_name.strip()
    if not q:
        return {"ok": False, "error": "Empty city name"}

    # geo.api.gouv.fr supports name search via /communes?nom=...; it may return multiple matches
    data = _get_json(
        f"{GEO_API}/communes",
        params={"nom": q, "fields": "code,nom,codeDepartement,codeRegion,population", "boost": "population", "limit": 5},
        read_timeout=20,
        retries=2,
    )
    # API returns a list
    if not isinstance(data, list) or not data:
        return {"ok": False, "error": f"No commune found for '{q}'"}

    best = data[0]
    return {
        "ok": True,
        "insee": best.get("code"),
        "nom": best.get("nom"),
        "code_departement": best.get("codeDepartement"),
        "code_region": best.get("codeRegion"),
        "population_geoapi": best.get("population"),
        "candidates": data,
    }


def fetch_commune_meta(insee: str) -> Dict[str, Any]:
    url = f"{GEO_API}/communes/{insee}"
    params = {"fields": "code,nom,codeDepartement,codeRegion,population,centre", "format": "json"}
    data = _get_json(url, params=params, read_timeout=20)
    return {
        "insee": data.get("code"),
        "nom": data.get("nom"),
        "code_departement": data.get("codeDepartement"),
        "code_region": data.get("codeRegion"),
        "population_geoapi": data.get("population"),
        "centre": data.get("centre"),
    }


# ---------------------------
# Population (public Opendatasoft)
# ---------------------------

def fetch_legal_population(insee: str, year: int | None = None) -> dict:
    url = "https://public.opendatasoft.com/api/records/1.0/search/"
    dataset = "demographyref-france-pop-legale-commune-arrondissement-municipal-millesime"

    probe = _get_json(url, params={"dataset": dataset, "q": "", "rows": 1}, read_timeout=20)
    records = probe.get("records", [])
    if not records:
        return {"ok": False, "error": "Population dataset returned no records"}

    fields = records[0]["fields"].keys()

    insee_fields = ["code_insee_commune", "insee_com", "code_commune_insee", "code_insee", "com_arm_code"]
    year_fields = ["millesime", "annee", "year", "geo_year", "census_year", "start_year"]
    pop_fields = ["pmun", "population", "pop_mun", "population_municipale", "poptot", "com_arm_pop_mun", "com_arm_pop_tot"]

    def pick(candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in fields:
                return c
        return None

    f_insee = pick(insee_fields)
    f_year = pick(year_fields)
    f_pop = pick(pop_fields)

    if not f_insee or not f_pop:
        return {"ok": False, "error": "Could not detect INSEE/pop fields", "fields_found": list(fields)}

    data = _get_json(
        url,
        params={"dataset": dataset, "q": "", "rows": 200, f"refine.{f_insee}": insee},
        read_timeout=20,
    )
    recs = data.get("records", [])
    if not recs:
        return {"ok": False, "error": f"No population record for INSEE={insee}"}

    chosen = None
    if year is not None and f_year:
        for r in recs:
            if str(r["fields"].get(f_year)) == str(year):
                chosen = r
                break

    if chosen is None and f_year:
        def year_key(r):
            try:
                return int(r["fields"].get(f_year))
            except Exception:
                return -1
        chosen = sorted(recs, key=year_key, reverse=True)[0]

    if chosen is None:
        chosen = recs[0]

    pop_val = chosen["fields"].get(f_pop)
    return {
        "ok": True,
        "dataset": dataset,
        "year_used": chosen["fields"].get(f_year) if f_year else None,
        "population": _try_int(pop_val),
        "fields": {"insee": f_insee, "year": f_year, "population": f_pop},
    }


# ---------------------------
# Enedis electricity (ODS Explore API v2.1)
# ---------------------------

def fetch_enedis_electricity(insee: str, year: int | None = None) -> dict:
    base = "https://opendata.enedis.fr/api/explore/v2.1/catalog/datasets"
    dataset = "consommation-electrique-par-secteur-dactivite-commune"
    url = f"{base}/{dataset}/records"

    probe = _get_json(url, params={"limit": 1}, read_timeout=30)
    results = probe.get("results", [])
    if not results:
        return {"ok": False, "error": "Enedis dataset probe returned no results"}

    keys0 = set(results[0].keys())
    f_insee = "code_commune" if "code_commune" in keys0 else None
    f_year = "annee" if "annee" in keys0 else None
    f_conso = "conso_totale_mwh" if "conso_totale_mwh" in keys0 else None

    if not f_insee or not f_year or not f_conso:
        return {"ok": False, "error": "Missing required fields", "fields_found": sorted(list(keys0))}

    # latest year available for this commune
    latest = _get_json(
        url,
        params={"where": f"{f_insee} = '{insee}'", "select": f"{f_year}", "order_by": f"{f_year} desc", "limit": 1},
        read_timeout=45,
    )
    latest_res = latest.get("results", [])
    if not latest_res:
        return {"ok": False, "error": f"No Enedis data for commune INSEE={insee}"}

    latest_year = latest_res[0].get(f_year)
    if latest_year is None:
        return {"ok": False, "error": "Could not read latest year from Enedis response", "sample": latest_res[0]}

    target_year = int(year) if year is not None else int(latest_year)
    if target_year > int(latest_year):
        target_year = int(latest_year)

    # Try multiple WHERE variants (ODS typing differs across portals)
    where_variants = [
        f"{f_insee} = '{insee}' AND {f_year} = {target_year}",         # your original
        f"{f_insee} = {int(insee)} AND {f_year} = {target_year}",      # both numeric
        f"{f_insee} = '{insee}' AND {f_year} = '{target_year}'",       # year as string
        f"{f_insee} = {int(insee)} AND {f_year} = '{target_year}'",    # mixed
    ]

    last_err: str | None = None
    for where in where_variants:
        try:
            data = _get_json(url, params={"where": where, "limit": 200}, read_timeout=60)
            recs = data.get("results", [])
            if not recs:
                last_err = f"No records with where={where}"
                continue

            total_mwh = 0.0
            for r in recs:
                fv = _try_float(r.get(f_conso))
                if fv is not None:
                    total_mwh += fv

            return {
                "ok": True,
                "dataset": dataset,
                "year": target_year,
                "latest_year_available": int(latest_year),
                "consumption_mwh": total_mwh,
                "consumption_kwh": total_mwh * 1000.0,
                "records_used": len(recs),
                "where": where,
            }
        except Exception as e:
            last_err = f"{type(e).__name__}: {e} (where={where})"
            continue

    return {
        "ok": False,
        "error": "Failed all Enedis where variants",
        "details": last_err,
        "tried": where_variants,
    }


# ---------------------------
# Air quality (OpenAQ v3, requires OPENAQ_API_KEY)
# ---------------------------

def fetch_air_quality_openaq(insee: str) -> dict:
    api_key = os.getenv("OPENAQ_API_KEY")
    if not api_key:
        return {"ok": False, "error": "Missing OPENAQ_API_KEY env var (OpenAQ v3 requires an API key)."}

    commune = _get_json(
        f"{GEO_API}/communes/{insee}",
        params={"fields": "nom,centre", "format": "json"},
        read_timeout=20,
        retries=2,
    )
    nom = commune.get("nom")
    centre = (commune.get("centre") or {}).get("coordinates")  # [lon, lat]
    if not centre or len(centre) != 2:
        return {"ok": False, "error": "No centre coordinates from geo.api.gouv.fr", "commune": commune}

    lon, lat = centre[0], centre[1]

    def _get_openaq(url: str, params: dict) -> dict:
        headers = {"X-API-Key": api_key, "Accept": "application/json", "User-Agent": "apicall.py/1.0"}
        r = requests.get(url, params=params, headers=headers, timeout=(10, 30))
        if r.status_code == 401:
            raise RuntimeError("OpenAQ 401 Unauthorized: API key missing/invalid (check OPENAQ_API_KEY).")
        r.raise_for_status()
        return r.json()

    locs = _get_openaq(
        "https://api.openaq.org/v3/locations",
        {"coordinates": f"{lat:.4f},{lon:.4f}", "radius": 25000, "limit": 5},
    )
    results = locs.get("results", [])
    if not results:
        return {"ok": False, "error": "No OpenAQ locations nearby", "lat": lat, "lon": lon}

    best = results[0]
    location_id = best.get("id")
    if not location_id:
        return {"ok": False, "error": "OpenAQ location missing id", "best_location": best}

    latest = _get_openaq(f"https://api.openaq.org/v3/locations/{location_id}/latest", {"limit": 200})
    measures = latest.get("results", [])

    out = []
    for m in measures:
        out.append({
            "parameter": m.get("parameter") or m.get("name"),  # OpenAQ payloads vary
            "datetime_utc": (m.get("datetime") or {}).get("utc") if isinstance(m.get("datetime"), dict) else m.get("datetime"),
            "value": m.get("value"),
            "unit": m.get("unit"),
            "coordinates": m.get("coordinates"),
        })

    return {
        "ok": True,
        "source": "openaq_v3",
        "commune": {"insee": insee, "nom": nom, "lat": lat, "lon": lon},
        "location": {
            "id": location_id,
            "name": best.get("name"),
            "locality": best.get("locality"),
            "country": best.get("country"),
            "coordinates": best.get("coordinates"),
        },
        "latest": out,
        "note": "Station measurements (not the official French ATMO index).",
    }


# ---------------------------
# Green level (Overpass + commune contour)
# (Imports are optional; apicall.py still works without shapely/pyproj.)
# ---------------------------

GREEN_FILTERS: List[Tuple[str, str]] = [
    ("leisure", "park"),
    ("landuse", "forest"),
    ("landuse", "grass"),
    ("landuse", "meadow"),
    ("natural", "wood"),
    ("natural", "grassland"),
]
OVERPASS_URL_DEFAULT = "https://overpass-api.de/api/interpreter"

def _green_available() -> bool:
    try:
        import shapely  # noqa: F401
        import pyproj   # noqa: F401
        return True
    except Exception:
        return False

def compute_green_level(insee: str, population: int = 0, simplify: float = 0.0003, overpass_url: str = OVERPASS_URL_DEFAULT, timeout_s: int = 180) -> dict:
    """
    Computes green area share using Overpass and the commune contour from geo.api.gouv.fr.
    Returns a dict; never raises if deps are missing (returns ok:false).
    """
    if not _green_available():
        return {"ok": False, "error": "Missing deps for green level. Install shapely + pyproj.", "hint": "pip install shapely pyproj"}

    from shapely.geometry import shape, Polygon, MultiPolygon, LinearRing, box
    from shapely.ops import transform
    from shapely.validation import make_valid
    from pyproj import Transformer

    def fetch_commune_contour_geom(code: str, timeout: int = 30):
        url = f"{GEO_API}/communes/{code}?format=geojson&geometry=contour"
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        gj = r.json()
        return shape(gj["geometry"])

    def ensure_polygon_like(geom):
        if isinstance(geom, (Polygon, MultiPolygon)):
            return geom
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

    def overpass_request(query: str, timeout: int = 240) -> dict:
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

    def union_area_km2(geoms: List[Polygon]) -> float:
        if not geoms:
            return 0.0
        u = geoms[0]
        for g in geoms[1:]:
            u = u.union(g)
        return wgs84_area_km2(u)

    try:
        geom_raw = fetch_commune_contour_geom(insee)
        commune_geom = ensure_polygon_like(geom_raw)
        commune_area = wgs84_area_km2(commune_geom)

        if isinstance(commune_geom, MultiPolygon):
            poly_geom = max(list(commune_geom.geoms), key=lambda g: g.area)
        else:
            poly_geom = commune_geom

        poly_str = polygon_to_overpass_poly(poly_geom, simplify_tolerance_deg=simplify)
        query = build_overpass_query(poly_str, timeout_s=timeout_s)
        osm = overpass_request(query, timeout=timeout_s + 30)

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
        score = max(0.0, min(100.0, 100.0 * (share_pct / 60.0)))  # 60%+ => 100

        out: dict = {
            "ok": True,
            "commune_area_km2": round(commune_area, 3),
            "green_area_km2": round(green_area, 3),
            "green_share_pct": round(share_pct, 2),
            "green_level_score_0_100": round(score, 1),
            "filters": [{"k": k, "v": v} for k, v in GREEN_FILTERS],
        }
        if population and population > 0:
            out["green_m2_per_person"] = round((green_area * 1e6) / population, 2)
        return out
    except Exception as e:
        return {"ok": False, "error": f"Green level failed: {type(e).__name__}: {e}"}


# ---------------------------
# Mobility (optional; depends on geopandas + local ADMIN_GPKG path)
# We keep it as a best-effort, because scriptallinone.py is batch-oriented.
# ---------------------------

def mobility_available() -> bool:
    try:
        import geopandas  # noqa: F401
        import pandas     # noqa: F401
        return True
    except Exception:
        return False

def fetch_mobility_for_insee(insee: str, admin_gpkg: str | None = None) -> dict:
    """
    Best-effort mobility metrics (bike lanes length + carpool areas) per commune.
    NOTE: requires geopandas/pandas AND a local ADMIN-EXPRESS GPKG (same as your scriptallinone.py).
    If not available, returns ok:false.
    """
    if not mobility_available():
        return {"ok": False, "error": "Missing deps for mobility. Install geopandas + pandas."}

    if not admin_gpkg:
        # default: same path as your scriptallinone.py (edit if needed)
        admin_gpkg = (
            "data/ADMIN-EXPRESS_4-0__GPKG_LAMB93_FXX_2025-12-05/"
            "ADMIN-EXPRESS/1_DONNEES_LIVRAISON_2025-12-00045/"
            "ADE_4-0_GPKG_LAMB93_FXX-ED2025-12-05/"
            "ADE_4-0_GPKG_LAMB93_FXX-ED2025-12-05.gpkg"
        )

    if not os.path.exists(admin_gpkg):
        return {"ok": False, "error": "ADMIN_GPKG not found on disk", "admin_gpkg": admin_gpkg}

    import pandas as pd
    import geopandas as gpd

    URL_PISTES = "https://www.data.gouv.fr/api/1/datasets/r/6078e5e3-a016-418c-9cea-e382be82dd7c"
    URL_COVOIT = "https://www.data.gouv.fr/api/1/datasets/r/4fd78dee-e122-4c0d-8bf6-ff55d79f3af1"

    # read communes layer
    communes = gpd.read_file(admin_gpkg, layer="COMMUNE")
    if "code_insee" not in communes.columns:
        # fallback column name
        for c in communes.columns:
            if c.lower().startswith("code_insee"):
                communes = communes.rename(columns={c: "code_insee"})
                break

    communes = communes.to_crs(epsg=2154)
    communes = communes[communes["code_insee"] == insee].copy()
    if communes.empty:
        return {"ok": False, "error": "INSEE not found in ADMIN_GPKG COMMUNE layer", "insee": insee}

    commune_geom = communes.geometry.iloc[0]
    surface_km2 = float(commune_geom.area / 1e6)

    # download datasets to temp (in-memory via requests)
    pistes_bytes = requests.get(URL_PISTES, timeout=60).content
    pistes = gpd.read_file(pistes_bytes).to_crs(epsg=2154)
    pistes["length_km"] = pistes.geometry.length / 1000.0
    pistes_in = pistes[pistes.intersects(commune_geom)]
    km_pistes = float(pistes_in["length_km"].sum()) if not pistes_in.empty else 0.0

    covoit_csv = requests.get(URL_COVOIT, timeout=60).content.decode("utf-8", errors="ignore")
    from io import StringIO
    covoit = pd.read_csv(StringIO(covoit_csv))
    lon, lat = "Xlong", "Ylat"
    if lon not in covoit.columns or lat not in covoit.columns:
        return {"ok": False, "error": "Unexpected carpool CSV columns", "columns": list(covoit.columns)}
    covoit_gdf = gpd.GeoDataFrame(
        covoit,
        geometry=gpd.points_from_xy(covoit[lon], covoit[lat]),
        crs="EPSG:4326"
    ).to_crs(epsg=2154)
    covoit_in = covoit_gdf[covoit_gdf.within(commune_geom)]
    nb_aires = int(len(covoit_in))

    cap_col = "nbre_pl" if "nbre_pl" in covoit.columns else None
    capacite = int(covoit_in[cap_col].sum()) if cap_col and nb_aires else nb_aires

    return {
        "ok": True,
        "surface_km2": round(surface_km2, 2),
        "velo": {
            "km_pistes": round(km_pistes, 2),
            "densite_km_km2": round(km_pistes / surface_km2, 3) if surface_km2 else 0,
        },
        "covoiturage": {
            "nb_aires": nb_aires,
            "capacite": capacite,
        },
        "admin_gpkg": admin_gpkg,
    }


# ---------------------------
# Main profile
# ---------------------------

def build_profile(city_name: str, year: int, include_green: bool, include_mobility: bool) -> dict:
    out: Dict[str, Any] = {
        "query": {"city_name": city_name, "year": year},
        "generated_at_utc": now_utc().isoformat(),
    }

    resolved = resolve_city_to_insee(city_name)
    out["resolved"] = resolved
    if not resolved.get("ok"):
        return out

    insee = resolved["insee"]
    out["insee"] = insee

    out["commune"] = fetch_commune_meta(insee)

    pop = fetch_legal_population(insee, year=year)
    out["population_legal"] = pop

    elec = fetch_enedis_electricity(insee, year=None)  # auto latest year
    out["electricity"] = elec

    if pop.get("ok") and elec.get("ok") and pop.get("population"):
        out["kwh_per_inhabitant"] = elec["consumption_kwh"] / float(pop["population"])
    else:
        out["kwh_per_inhabitant"] = None

    # Air quality (best effort)
    try:
        out["air_quality_today"] = fetch_air_quality_openaq(insee)
    except Exception as e:
        out["air_quality_today"] = {"ok": False, "error": f"OpenAQ failed: {type(e).__name__}: {e}"}

    # Green level (best effort)
    if include_green:
        population_for_green = pop.get("population") if pop.get("ok") else 0
        out["green_level"] = compute_green_level(insee, population=int(population_for_green or 0))
    else:
        out["green_level"] = {"ok": False, "skipped": True}

    # Mobility (best effort)
    if include_mobility:
        out["mobility"] = fetch_mobility_for_insee(insee)
    else:
        out["mobility"] = {"ok": False, "skipped": True}

    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Merged API calls by city name -> JSON profile.")
    p.add_argument("cityname", help='City name (commune), e.g. "Rennes"')
    p.add_argument("--year", type=int, default=(now_utc().year - 1), help="Population reference year (default: current_year-1)")
    p.add_argument("--no-green", action="store_true", help="Skip green level (Overpass/shapely).")
    p.add_argument("--no-mobility", action="store_true", help="Skip mobility (geopandas + local ADMIN_GPKG).")
    args = p.parse_args()

    profile = build_profile(
        args.cityname,
        year=args.year,
        include_green=not args.no_green,
        include_mobility=not args.no_mobility,
    )
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
