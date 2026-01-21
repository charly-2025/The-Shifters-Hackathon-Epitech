#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime as dt
import json
import sys
import time
from typing import Any, Dict, Optional, List

import requests

UTC = dt.timezone.utc


# ---------------------------
# HTTP helpers (retry + timeouts)
# ---------------------------

def _get_json(
    url: str,
    params: dict | None = None,
    read_timeout: int = 30,
    retries: int = 2,
    backoff: float = 1.6,
) -> dict:
    import time
    import requests
    import json as _json

    headers = {
        "User-Agent": "eco-city-script/1.0 (+https://example.local)",
        "Accept": "application/json,text/plain,*/*",
    }

    last_exc = None
    last_text = None
    last_loc = None

    for i in range(retries):
        try:
            r = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=(10, read_timeout),
                allow_redirects=False,   # <- important
            )

            # si redirect, on capture la location pour debug
            if 300 <= r.status_code < 400:
                last_loc = r.headers.get("Location")
                raise RuntimeError(f"Redirect {r.status_code} to {last_loc}")

            r.raise_for_status()
            text = r.text
            last_text = text[:300]

            ct = (r.headers.get("Content-Type") or "").lower()
            if "application/json" in ct or text.lstrip().startswith("{") or text.lstrip().startswith("["):
                return r.json()

            # tentative parse
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
# 1) Commune metadata by INSEE
# ---------------------------

def fetch_commune_meta(insee: str) -> Dict[str, Any]:
    url = f"https://geo.api.gouv.fr/communes/{insee}"
    params = {"fields": "code,nom,codeDepartement,codeRegion,population", "format": "json"}
    data = _get_json(url, params=params, read_timeout=20)
    return {
        "insee": data.get("code"),
        "nom": data.get("nom"),
        "code_departement": data.get("codeDepartement"),
        "code_region": data.get("codeRegion"),
        "population_geoapi": data.get("population"),
    }


# ---------------------------
# 2) Legal population (public Opendatasoft)
# ---------------------------

def fetch_legal_population(insee: str, year: int | None = None) -> dict:
    url = "https://public.opendatasoft.com/api/records/1.0/search/"
    dataset = "demographyref-france-pop-legale-commune-arrondissement-municipal-millesime"

    probe = _get_json(url, params={"dataset": dataset, "q": "", "rows": 1}, read_timeout=20)
    records = probe.get("records", [])
    if not records:
        return {"ok": False, "error": "Population dataset returned no records"}

    fields = records[0]["fields"].keys()

    # ✅ Ajout des champs réellement présents dans ton retour
    insee_fields = [
        "code_insee_commune", "insee_com", "code_commune_insee", "code_insee",
        "com_arm_code"  # <- ton cas
    ]
    year_fields = [
        "millesime", "annee", "year",
        "geo_year", "census_year", "start_year"  # <- ton cas
    ]
    pop_fields = [
        "pmun", "population", "pop_mun", "population_municipale", "poptot",
        "com_arm_pop_mun", "com_arm_pop_tot"  # <- ton cas
    ]

    def pick(candidates):
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

def fetch_population_with_plm_override(insee: str, year: int | None = None) -> dict:
    """
    Fetch legal population.
    Special-case Paris / Lyon / Marseille with hardcoded official values
    to avoid arrondissement aggregation issues.
    """

    # Official INSEE legal populations (latest known, commune-level)
    PLM_POPULATION = {
        "75056": {  # Paris
            "population": 2165423,
            "year": 2022,
            "name": "Paris",
        },
        "69123": {  # Lyon
            "population": 522250,
            "year": 2022,
            "name": "Lyon",
        },
        "13055": {  # Marseille
            "population": 870018,
            "year": 2022,
            "name": "Marseille",
        },
    }

    if insee in PLM_POPULATION:
        p = PLM_POPULATION[insee]
        return {
            "ok": True,
            "population": p["population"],
            "year_used": p["year"],
            "note": f"Hardcoded official INSEE population for {p['name']} (PLM commune).",
            "confidence": "high",
        }

    # Default: normal dynamic lookup
    return fetch_legal_population(insee, year=year)

# ---------------------------
# 3) Enedis electricity consumption (ODS Explore API v2.1)
# ---------------------------

def fetch_enedis_electricity(insee: str, year: int | None = None) -> dict:
    """
    Récupère la conso électrique totale (MWh) pour une commune.
    Si year=None ou si l'année demandée n'existe pas, on prend la dernière année dispo.
    """
    base = "https://opendata.enedis.fr/api/explore/v2.1/catalog/datasets"
    dataset = "consommation-electrique-par-secteur-dactivite-commune"
    url = f"{base}/{dataset}/records"

    probe = _get_json(url, params={"limit": 1}, read_timeout=30)
    results = probe.get("results", [])
    if not results:
        return {"ok": False, "error": "Enedis dataset probe returned no results"}

    keys0 = set(results[0].keys())

    # champs réels (d'après ton retour)
    f_insee = "code_commune" if "code_commune" in keys0 else None
    f_year = "annee" if "annee" in keys0 else None
    f_conso = "conso_totale_mwh" if "conso_totale_mwh" in keys0 else None

    if not f_insee or not f_year or not f_conso:
        return {"ok": False, "error": "Missing required fields", "fields_found": sorted(list(keys0))}

    # 1) Trouver la dernière année dispo pour cette commune
    # On trie par annee DESC et on prend 1 record
    where_latest = f"{f_insee} = '{insee}'"
    latest = _get_json(
        url,
        params={"where": where_latest, "select": f"{f_year}", "order_by": f"{f_year} desc", "limit": 1},
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

    # 2) Récupérer toutes les lignes pour cette année+commune et sommer
    where = f"{f_insee} = '{insee}' AND {f_year} = {target_year}"
    data = _get_json(url, params={"where": where, "limit": 100}, read_timeout=60)
    recs = data.get("results", [])
    if not recs:
        return {"ok": False, "error": f"No Enedis records for INSEE={insee}, year={target_year}", "where": where}

    total_mwh = 0.0
    for r in recs:
        v = r.get(f_conso)
        fv = _try_float(v)
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

# ---------------------------
# 4) ATMO index today via WFS (best effort)
# ---------------------------

def fetch_atmo_index_today(insee: str) -> dict:
    """
    Version stable via Opendatasoft (Atmo Data) au lieu de GeoServer.
    On cherche une zone contenant le nom de la commune (Rennes) et on prend la dernière date dispo.
    """
    # Nom commune
    try:
        commune_name = (fetch_commune_meta(insee).get("nom") or "Rennes").strip()
    except Exception:
        commune_name = "Rennes"

    # Endpoint ODS Atmo Data (catalog v2)
    base = "https://data.atmo-france.org/api/explore/v2.1/catalog/datasets"
    dataset = "ind_atmo"  # nom court probable côté ODS
    url = f"{base}/{dataset}/records"

    # 1) probe pour vérifier que le dataset existe
    try:
        probe = _get_json(url, params={"limit": 1}, read_timeout=30, retries=2)
    except Exception as e:
        return {"ok": False, "error": f"Atmo ODS dataset not reachable: {type(e).__name__}: {e}", "tried": url}

    results = probe.get("results", [])
    if not results:
        return {"ok": False, "error": "Atmo ODS probe returned no results", "dataset": dataset}

    keys = set(results[0].keys())

    # Champs attendus (on s'adapte)
    # On a vu côté GeoServer: code_zone, lib_zone, date_ech, lib_qual, code_qual, coul_qual, etc.
    def pick(cands):
        for c in cands:
            if c in keys:
                return c
        return None

    f_zone_code = pick(["code_zone", "zone_code"])
    f_zone_name = pick(["lib_zone", "zone_name", "nom_zone"])
    f_date = pick(["date_ech", "date", "date_maj", "date_dif"])
    f_lib_qual = pick(["lib_qual", "qualite", "libelle_qualite"])
    f_code_qual = pick(["code_qual", "indice", "code_indice"])
    f_color = pick(["coul_qual", "couleur"])

    if not f_zone_code or not f_zone_name or not f_date:
        return {"ok": False, "error": "Could not detect required fields in Atmo ODS", "fields_found": sorted(list(keys))}

    # 2) requête: zones dont le nom contient Rennes, tri par date desc, prendre 1
    # ODS v2: where + order_by
    where = f"{f_zone_name} ILIKE '%{commune_name}%'"
    data = _get_json(
        url,
        params={"where": where, "order_by": f"{f_date} desc", "limit": 1},
        read_timeout=45,
        retries=2,
    )
    recs = data.get("results", [])
    if not recs:
        # fallback sans ILIKE (au cas où ODS n'accepte pas ILIKE): contains lower
        where2 = f"lower({f_zone_name}) like '%{commune_name.lower()}%'"
        data2 = _get_json(
            url,
            params={"where": where2, "order_by": f"{f_date} desc", "limit": 1},
            read_timeout=45,
            retries=2,
        )
        recs = data2.get("results", [])
        if not recs:
            return {"ok": False, "error": "No Atmo ODS record matched this commune name", "commune_name": commune_name, "where": where}

    r = recs[0]
    return {
        "ok": True,
        "dataset": dataset,
        "zone": {"code_zone": r.get(f_zone_code), "lib_zone": r.get(f_zone_name)},
        "date": r.get(f_date),
        "lib_qual": r.get(f_lib_qual) if f_lib_qual else None,
        "code_qual": r.get(f_code_qual) if f_code_qual else None,
        "color": r.get(f_color) if f_color else None,
        "raw": r,
    }


    # Heuristique: choisir la meilleure zone
    def score(p):
        name = (p.get("lib_zone") or "").lower()
        t = (p.get("type_zone") or "").lower()
        s = 0
        if commune_name_lc in name:
            s += 5
        if "agglo" in t or "urba" in t or "metropole" in name:
            s += 2
        return s

    best = sorted(candidates, key=score, reverse=True)[0]
    code_zone = best.get("code_zone")
    lib_zone = best.get("lib_zone")
    type_zone = best.get("type_zone")

    if not code_zone:
        return {"ok": False, "error": "Matched zone but missing code_zone", "best_zone": best}

    # 3) Récupérer la valeur du jour pour cette zone (CQL simple sur code_zone + date)
    cql_today = f"code_zone='{code_zone}' AND date_ech >= '{start_z}' AND date_ech < '{end_z}'"

    day_data = _get_json(
        base,
        params={
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": type_name,
            "outputFormat": "application/json",
            "CQL_FILTER": cql_today,
            "count": 20,
        },
        read_timeout=90,
        retries=2,
    )

    day_feats = day_data.get("features", [])
    if not day_feats:
        # fallback: prendre la dernière dispo pour cette zone (sans fenêtre jour)
        cql_latest_zone = f"code_zone='{code_zone}'"
        zdata = _get_json(
            base,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": type_name,
                "outputFormat": "application/json",
                "CQL_FILTER": cql_latest_zone,
                "count": 1,
                "sortBy": "date_ech D",
            },
            read_timeout=90,
            retries=2,
        )
        zfeats = zdata.get("features", [])
        if not zfeats:
            return {
                "ok": False,
                "error": "Zone found but no data for it",
                "zone": {"code_zone": code_zone, "lib_zone": lib_zone, "type_zone": type_zone},
            }
        props = zfeats[0].get("properties", {})
        return {
            "ok": True,
            "dataset": type_name,
            "zone": {"code_zone": code_zone, "lib_zone": lib_zone, "type_zone": type_zone},
            "note": "No feature in today's window; returned latest available for this zone instead.",
            "date_ech": props.get("date_ech"),
            "lib_qual": props.get("lib_qual"),
            "code_qual": props.get("code_qual"),
            "coul_qual": props.get("coul_qual"),
            "codes_polluants": {
                "pm10": props.get("code_pm10"),
                "pm25": props.get("code_pm25"),
                "no2": props.get("code_no2"),
                "o3": props.get("code_o3"),
                "so2": props.get("code_so2"),
            },
            "properties": props,
        }

    props = day_feats[0].get("properties", {})
    return {
        "ok": True,
        "dataset": type_name,
        "zone": {"code_zone": code_zone, "lib_zone": lib_zone, "type_zone": type_zone},
        "date_ech": props.get("date_ech"),
        "lib_qual": props.get("lib_qual"),
        "code_qual": props.get("code_qual"),
        "coul_qual": props.get("coul_qual"),
        "codes_polluants": {
            "pm10": props.get("code_pm10"),
            "pm25": props.get("code_pm25"),
            "no2": props.get("code_no2"),
            "o3": props.get("code_o3"),
            "so2": props.get("code_so2"),
        },
        "properties": props,
    }

def _clean_openaq_latest(latest: list) -> dict:  #CLEAN UP AND MAKE A BETTER LOOKING JSON
    """
    Take OpenAQ 'latest' list and return a compact dict:
    { "pm25": {"value": 8.1, "unit":"µg/m³"}, ... }
    Strips datetime/coords/ids.
    """
    out: dict = {}
    if not isinstance(latest, list):
        return out

    for m in latest:
        # Try to infer a parameter name if present
        param = m.get("parameter") or m.get("name")
        if not param:
            # fallback: some payloads don’t include it; skip
            continue

        val = m.get("value")
        unit = m.get("unit")
        # Keep first occurrence per parameter
        if param not in out and val is not None:
            out[param] = {"value": val, "unit": unit}
    return out


def make_eco_digest(profile: dict) -> dict:
    """
    Build a small, human-friendly ecological summary from the full profile.
    """
    digest: dict = {"ok": True}

    commune = profile.get("commune") or {}
    digest["commune"] = {
        "insee": profile.get("insee") or commune.get("insee"),
        "name": commune.get("nom"),
        "departement": commune.get("code_departement"),
        "region": commune.get("code_region"),
    }

    pop = profile.get("population_legal") or {}
    if pop.get("ok"):
        digest["population"] = {
            "value": pop.get("population"),
            "year": pop.get("year_used"),
        }
    else:
        digest["population"] = {"ok": False, "error": pop.get("error")}

    elec = profile.get("electricity") or {}
    if elec.get("ok"):
        digest["electricity"] = {
            "year": elec.get("year"),
            "consumption_mwh": round(float(elec.get("consumption_mwh") or 0.0), 2),
        }
    else:
        digest["electricity"] = {"ok": False, "error": elec.get("error")}

    kwh_i = profile.get("kwh_per_inhabitant")
    digest["kwh_per_inhabitant"] = round(float(kwh_i), 1) if kwh_i is not None else None

        # Green level (if present)
    green = profile.get("green_level") or {}
    if green.get("ok"):
        digest["green_level"] = {
            "green_share_pct": green.get("green_share_pct"),
            "green_m2_per_person": green.get("green_m2_per_person"),
            "score_0_100": green.get("green_level_score_0_100"),
        }
    else:
        # show error only if it exists (keeps output clean)
        if green:
            digest["green_level"] = {"ok": False, "error": green.get("error")}


    air = profile.get("air_quality_today") or {}
    if air.get("ok"):
        digest["air_quality"] = {
            "source": air.get("source"),
            "station": (air.get("location") or {}).get("name"),
            "pollutants": _clean_openaq_latest(air.get("latest") or []),
            "note": air.get("note"),
        }
    else:
        digest["air_quality"] = {"ok": False, "error": air.get("error")}

    return digest

# Profile builder
# ---------------------------
def fetch_air_quality_openaq(insee: str) -> dict:
    """
    Qualité de l'air via OpenAQ v3 (nécessite OPENAQ_API_KEY).
    Correct approach:
      - Find nearest location
      - Query /v3/locations/{id}/sensors (contains parameter name + units + latest value)
    Returns ecology-only fields: parameter, value, unit.
    """
    import os
    import requests

    api_key = os.getenv("OPENAQ_API_KEY")
    if not api_key:
        return {"ok": False, "error": "Missing OPENAQ_API_KEY env var (OpenAQ v3 requires an API key)."}

    # 1) coords from geo.api.gouv.fr
    commune = _get_json(
        f"https://geo.api.gouv.fr/communes/{insee}",
        params={"fields": "nom,centre", "format": "json"},
        read_timeout=20,
        retries=2,
    )
    nom = (commune.get("nom") or "").strip()
    centre = (commune.get("centre") or {}).get("coordinates")  # [lon, lat]
    if not centre or len(centre) != 2:
        return {"ok": False, "error": "No centre coordinates from geo.api.gouv.fr", "commune": commune}

    lon, lat = centre[0], centre[1]

    def _get_openaq(url: str, params: dict) -> dict:
        headers = {
            "X-API-Key": api_key,
            "Accept": "application/json",
            "User-Agent": "eco-city/1.0",
        }
        r = requests.get(url, params=params, headers=headers, timeout=(10, 30))
        if r.status_code == 401:
            raise RuntimeError("OpenAQ 401 Unauthorized: API key missing/invalid (check OPENAQ_API_KEY).")
        r.raise_for_status()
        return r.json()

    # 2) nearest locations
    locs = _get_openaq(
        "https://api.openaq.org/v3/locations",
        {"coordinates": f"{lat:.4f},{lon:.4f}", "radius": 25000, "limit": 10},
    )
    results = locs.get("results", [])
    if not results:
        return {"ok": False, "error": "No OpenAQ locations nearby", "lat": lat, "lon": lon}

    best = results[0]
    location_id = best.get("id")
    if not location_id:
        return {"ok": False, "error": "OpenAQ location missing id", "best_location": best}

    # 3) sensors at that location (this is where parameter name + units live)
    sensors_payload = _get_openaq(
        f"https://api.openaq.org/v3/locations/{location_id}/sensors",
        {"limit": 200},
    )
    sensors = sensors_payload.get("results", [])
    if not isinstance(sensors, list) or not sensors:
        return {
            "ok": True,
            "source": "openaq_v3",
            "commune": {"insee": insee, "nom": nom},
            "location": {
                "id": location_id,
                "name": best.get("name"),
                "locality": best.get("locality"),
                "country": best.get("country"),
            },
            "latest": [],
            "note": "No sensors returned for this location.",
        }

    # Optional: keep only common air pollutants (drop humidity/temp etc.)
    keep = {"pm25", "pm10", "no2", "o3", "so2", "co", "bc", "nh3"}

    out = []
    for s in sensors:
        param = (s.get("parameter") or {})
        pname = param.get("name")  # e.g. "pm25"
        unit = param.get("units")  # e.g. "µg/m³"
        latest = s.get("latest") or {}
        value = latest.get("value")

        if not pname or value is None:
            continue
        if pname not in keep:
            continue

        out.append({"parameter": pname, "value": value, "unit": unit})

    return {
        "ok": True,
        "source": "openaq_v3",
        "commune": {"insee": insee, "nom": nom},
        "location": {
            "id": location_id,
            "name": best.get("name"),
            "locality": best.get("locality"),
            "country": best.get("country"),
        },
        "latest": out,
        "note": "Données brutes de stations (pas l'indice ATMO officiel).",
    }

# FUNCTION GREEN LEVEL 

def compute_green_level(
    insee: str,
    population: int = 0,
    simplify: float = 0.0003,
    overpass_url: str = "https://overpass-api.de/api/interpreter",
    timeout_s: int = 180,
) -> dict:
    """
    Compute green area share for a commune using:
      - geo.api.gouv.fr contour geometry
      - Overpass API with GREEN_FILTERS
    Returns a dict; never raises (returns ok:false on error).

    Output (example):
      {
        "ok": true,
        "commune_area_km2": 50.39,
        "green_area_km2": 18.22,
        "green_share_pct": 36.2,
        "green_level_score_0_100": 60.3,
        "green_m2_per_person": 81.9
      }
    """
    try:
        from shapely.geometry import shape, Polygon, MultiPolygon, LinearRing, box
        from shapely.ops import transform
        from shapely.validation import make_valid
        from pyproj import Transformer
        import requests
    except Exception as e:
        return {"ok": False, "error": f"Missing deps for green level: {type(e).__name__}: {e}", "hint": "pip install shapely pyproj"}

    GEO_API = "https://geo.api.gouv.fr"
    GREEN_FILTERS = [
        ("leisure", "park"),
        ("landuse", "forest"),
        ("landuse", "grass"),
        ("landuse", "meadow"),
        ("natural", "wood"),
        ("natural", "grassland"),
    ]

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
        if simplify_tolerance_deg and simplify_tolerance_deg > 0:
            geom = geom.simplify(simplify_tolerance_deg, preserve_topology=True)
        coords = list(geom.exterior.coords)
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

    def overpass_request(query: str, timeout: int) -> dict:
        r = requests.post(overpass_url, data={"data": query}, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def element_to_polygon(el):
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

    def union_area_km2(geoms):
        geoms = list(geoms)
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

        # Overpass needs a Polygon ring; take largest polygon if multipolygon
        if commune_geom.geom_type == "MultiPolygon":
            poly_geom = max(list(commune_geom.geoms), key=lambda g: g.area)
        else:
            poly_geom = commune_geom

        poly_str = polygon_to_overpass_poly(poly_geom, simplify_tolerance_deg=simplify)
        query = build_overpass_query(poly_str, timeout_s=timeout_s)

        osm = overpass_request(query, timeout=timeout_s + 30)

        greens = []
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
        score = max(0.0, min(100.0, 100.0 * (share_pct / 60.0)))  # heuristic

        out = {
            "ok": True,
            "commune_area_km2": round(commune_area, 2),
            "green_area_km2": round(green_area, 2),
            "green_share_pct": round(share_pct, 1),
            "green_level_score_0_100": round(score, 1),
        }
        if population and population > 0:
            out["green_m2_per_person"] = round((green_area * 1e6) / population, 1)

        return out

    except Exception as e:
        return {
            "ok": False,
            "error": f"Green level failed: {type(e).__name__}: {e}",
            "hint": "Try simplify=0.001 or increase timeout_s, or change overpass_url.",
        }

###END OF GREEN LEVEL FUNCTION
def resolve_city_to_insee(city_or_insee: str) -> dict:
    """
    Accepts either an INSEE code (5 digits) or a French commune name.
    Returns {ok:True, insee:".....", nom:"..."} or {ok:False, error:"..."}.
    """
    q = (city_or_insee or "").strip()
    if not q:
        return {"ok": False, "error": "Empty city name / INSEE code"}

    # If it looks like an INSEE code already
    if q.isdigit() and len(q) == 5:
        try:
            meta = fetch_commune_meta(q)
            if meta.get("insee"):
                return {"ok": True, "insee": q, "nom": meta.get("nom")}
        except Exception:
            pass
        return {"ok": True, "insee": q, "nom": None}

    # Otherwise treat it as a commune name
    data = _get_json(
        "https://geo.api.gouv.fr/communes",
        params={
            "nom": q,
            "fields": "code,nom,codeDepartement,codeRegion,population",
            "boost": "population",
            "limit": 5,
        },
        read_timeout=20,
        retries=2,
    )

    if not isinstance(data, list) or not data:
        return {"ok": False, "error": f"No commune found for '{q}'"}

    best = data[0]
    return {
        "ok": True,
        "insee": best.get("code"),
        "nom": best.get("nom"),
        "candidates": data,
    }


def ecological_profile(insee: str, energy_year: int, energy_sector: Optional[str] = None) -> dict:
    out: Dict[str, Any] = {
        "insee": insee,
        "generated_at_utc": now_utc().isoformat(),
    }

    out["commune"] = fetch_commune_meta(insee)

    pop = fetch_population_with_plm_override(insee, year=energy_year)
    out["population_legal"] = pop

    elec = fetch_enedis_electricity(insee, year=None)
    out["electricity"] = elec

    if pop.get("ok") and elec.get("ok") and pop.get("population"):
        out["kwh_per_inhabitant"] = (
            elec["consumption_kwh"] / float(pop["population"])
        )
    else:
        out["kwh_per_inhabitant"] = None

    # ---------------------------
    # Green level (best effort)
    # ---------------------------
    try:
        population_for_green = pop.get("population") if pop.get("ok") else 0
        out["green_level"] = compute_green_level(
            insee,
            population=int(population_for_green or 0),
        )
    except Exception as e:
        out["green_level"] = {
            "ok": False,
            "error": f"Green level failed: {type(e).__name__}: {e}",
        }

    # ---------------------------
    # Air quality (best effort)
    # ---------------------------
    try:
        out["air_quality_today"] = fetch_air_quality_openaq(insee)
    except Exception as e:
        out["air_quality_today"] = {
            "ok": False,
            "error": f"OpenAQ failed: {type(e).__name__}: {e}",
        }

    return out


def eco_city(query: str) -> dict:
    resolved = resolve_city_to_insee(query)
    if not resolved.get("ok"):
        return {"ok": False, "error": resolved.get("error")}

    insee = resolved["insee"]
    year = now_utc().year - 1

    result = ecological_profile(insee, energy_year=year)
    digest = make_eco_digest(result)

    digest["resolved_from"] = {
        "query": query,
        "insee": insee,
        "name": resolved.get("nom"),
    }

    return digest


# ---------------------------
# CLI
# ---------------------------

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Rennes"
    output = eco_city(query)
    print(json.dumps(output, ensure_ascii=False, indent=2))
