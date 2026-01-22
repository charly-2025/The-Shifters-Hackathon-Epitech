import datetime as dt
import json
import sys
import os
import requests
from typing import Optional

UTC = dt.timezone.utc

def _get_json(url: str, params: dict = None, timeout: int = 30) -> dict:
    headers = {
        "User-Agent": "eco-city-script/1.0",
        "Accept": "application/json",
    }
    
    r = requests.get(url, params=params, headers=headers, timeout=(10, timeout))
    r.raise_for_status()
    return r.json()

def fetch_commune_meta(insee: str) -> dict:
    url = f"https://geo.api.gouv.fr/communes/{insee}"
    params = {"fields": "code,nom,codeDepartement,codeRegion,population,centre", "format": "json"}
    data = _get_json(url, params)
    return {
        "insee": data.get("code"),
        "nom": data.get("nom"),
        "code_departement": data.get("codeDepartement"),
        "code_region": data.get("codeRegion"),
        "population": data.get("population"),
        "centre": data.get("centre", {}).get("coordinates"),
    }


def fetch_population(insee: str) -> dict:
    PLM = {
        "75056": {"population": 2165423, "year": 2022, "name": "Paris"},
        "69123": {"population": 522250, "year": 2022, "name": "Lyon"},
        "13055": {"population": 870018, "year": 2022, "name": "Marseille"},
    }
    
    if insee in PLM:
        p = PLM[insee]
        return {"ok": True, "population": p["population"], "year": p["year"]}
    
    url = "https://public.opendatasoft.com/api/records/1.0/search/"
    dataset = "demographyref-france-pop-legale-commune-arrondissement-municipal-millesime"
    
    data = _get_json(url, {"dataset": dataset, "q": "", "rows": 200, f"refine.com_arm_code": insee})
    records = data.get("records", [])
    
    if not records:
        return {"ok": False, "error": "No population data"}
    
    
    chosen = max(records, key=lambda r: int(r["fields"].get("geo_year", 0)))
    
    return {
        "ok": True,
        "population": int(chosen["fields"].get("com_arm_pop_mun", 0)),
        "year": chosen["fields"].get("geo_year"),
    }


def fetch_electricity(insee: str) -> dict:
    base = "https://opendata.enedis.fr/api/explore/v2.1/catalog/datasets"
    dataset = "consommation-electrique-par-secteur-dactivite-commune"
    url = f"{base}/{dataset}/records"
    
    where = f"code_commune = '{insee}'"
    latest = _get_json(url, {"where": where, "select": "annee", "order_by": "annee desc", "limit": 1})
    
    if not latest.get("results"):
        return {"ok": False, "error": "No electricity data"}
    
    year = latest["results"][0]["annee"]
    
    
    data = _get_json(url, {"where": f"{where} AND annee = {year}", "limit": 100})
    
    total_mwh = sum(float(r.get("conso_totale_mwh", 0)) for r in data.get("results", []))
    
    return {
        "ok": True,
        "year": year,
        "consumption_mwh": round(total_mwh, 2),
        "consumption_kwh": round(total_mwh * 1000, 2),
    }


def fetch_air_quality(insee: str, commune_meta: dict) -> dict:
    api_key = os.getenv("OPENAQ_API_KEY")
    if not api_key:
        return {"ok": False, "error": "Missing OPENAQ_API_KEY"}
    
    centre = commune_meta.get("centre")
    if not centre:
        return {"ok": False, "error": "No coordinates"}
    
    lon, lat = centre[0], centre[1]
    headers = {"X-API-Key": api_key, "Accept": "application/json"}
    
    
    locs = requests.get(
        "https://api.openaq.org/v3/locations",
        params={"coordinates": f"{lat:.4f},{lon:.4f}", "radius": 25000, "limit": 1},
        headers=headers,
        timeout=30,
    ).json()
    
    results = locs.get("results", [])
    if not results:
        return {"ok": False, "error": "No nearby stations"}
    
    location = results[0]
    location_id = location.get("id")
    
    
    sensors = requests.get(
        f"https://api.openaq.org/v3/locations/{location_id}/sensors",
        params={"limit": 200},
        headers=headers,
        timeout=30,
    ).json()
    
   
    pollutants = {}
    for s in sensors.get("results", []):
        param = s.get("parameter", {})
        pname = param.get("name")
        if pname in {"pm25", "pm10", "no2", "o3", "so2", "co"}:
            latest = s.get("latest", {})
            value = latest.get("value")
            if value is not None:
                pollutants[pname] = {"value": value, "unit": param.get("units")}
    
    return {
        "ok": True,
        "station": location.get("name"),
        "pollutants": pollutants,
    }


def compute_green_level(insee: str, population: int) -> dict:
    try:
        from shapely.geometry import shape, Polygon, MultiPolygon, LinearRing
        from shapely.ops import transform
        from pyproj import Transformer
    except ImportError:
        return {"ok": False, "error": "pip install shapely pyproj"}
    
    
    url = f"https://geo.api.gouv.fr/communes/{insee}?format=geojson&geometry=contour"
    geojson = requests.get(url, timeout=30).json()
    geom = shape(geojson["geometry"])
    
    to_l93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    geom_l93 = transform(to_l93.transform, geom)
    commune_area_km2 = geom_l93.area / 1e6
 
    if isinstance(geom, MultiPolygon):
        poly = max(geom.geoms, key=lambda g: g.area)
    else:
        poly = geom
    
    coords = " ".join([f"{lat:.6f} {lon:.6f}" for lon, lat in poly.exterior.coords])
    
    query = f"""
[out:json][timeout:180];
(
  way["leisure"="park"](poly:"{coords}");
  way["landuse"="forest"](poly:"{coords}");
  way["landuse"="grass"](poly:"{coords}");
  way["natural"="wood"](poly:"{coords}");
);
out geom;
"""
    
    osm = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        timeout=200,
    ).json()
    
    
    green_polys = []
    for el in osm.get("elements", []):
        coords_list = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        if len(coords_list) >= 4:
            if coords_list[0] != coords_list[-1]:
                coords_list.append(coords_list[0])
            try:
                green_polys.append(Polygon(coords_list))
            except:
                pass
    
    if not green_polys:
        green_area_km2 = 0.0
    else:
        union = green_polys[0]
        for p in green_polys[1:]:
            union = union.union(p)
        clipped = union.intersection(geom)
        clipped_l93 = transform(to_l93.transform, clipped)
        green_area_km2 = clipped_l93.area / 1e6
    
    share_pct = (100.0 * green_area_km2 / commune_area_km2) if commune_area_km2 else 0.0
    score = min(100.0, 100.0 * (share_pct / 60.0))
    
    return {
        "ok": True,
        "commune_area_km2": round(commune_area_km2, 2),
        "green_area_km2": round(green_area_km2, 2),
        "green_share_pct": round(share_pct, 1),
        "score_0_100": round(score, 1),
        "green_m2_per_person": round((green_area_km2 * 1e6) / population, 1) if population else None,
    }

def resolve_city(query: str) -> dict:
    q = query.strip()
    
    if q.isdigit() and len(q) == 5:
        return {"ok": True, "insee": q}
    
    
    data = _get_json(
        "https://geo.api.gouv.fr/communes",
        {"nom": q, "fields": "code,nom", "boost": "population", "limit": 1},
    )
    
    if not data:
        return {"ok": False, "error": f"No commune found for '{q}'"}
    
    return {"ok": True, "insee": data[0]["code"], "nom": data[0]["nom"]}


def eco_city(query: str, skip_slow: bool = False) -> dict:
    """
    Args:
        query: Nom de ville ou code INSEE
        skip_slow: Si True, ignore les calculs lents (green_level)
    """
    resolved = resolve_city(query)
    if not resolved.get("ok"):
        return resolved
    
    insee = resolved["insee"]
    
    commune = fetch_commune_meta(insee)
    pop = fetch_population(insee)
    elec = fetch_electricity(insee)
    
    
    kwh_per_person = None
    if pop.get("ok") and elec.get("ok") and pop.get("population"):
        kwh_per_person = round(elec["consumption_kwh"] / pop["population"], 1)
    
    if skip_slow:
        green = {"ok": False, "skipped": True, "reason": "skip_slow=True"}
    elif pop.get("ok"):
        try:
            green = compute_green_level(insee, pop.get("population", 0))
        except Exception as e:
            green = {"ok": False, "error": str(e)}
    else:
        green = {"ok": False}
    
    air = fetch_air_quality(insee, commune)
    
    return {
        "ok": True,
        "commune": {
            "insee": insee,
            "name": commune["nom"],
            "departement": commune["code_departement"],
            "region": commune["code_region"],
        },
        "population": {
            "value": pop.get("population"),
            "year": pop.get("year"),
        } if pop.get("ok") else {"ok": False},
        "electricity": {
            "year": elec.get("year"),
            "consumption_mwh": elec.get("consumption_mwh"),
        } if elec.get("ok") else {"ok": False},
        "kwh_per_inhabitant": kwh_per_person,
        "green_level": green if green.get("ok") else {"ok": False},
        "air_quality": air if air.get("ok") else {"ok": False},
    }

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Rennes"
    output = eco_city(query)
    print(json.dumps(output, ensure_ascii=False, indent=2))