#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime as dt
import json
import sys
from typing import Any, Dict, Optional, Tuple, List

import requests


# ---------------------------
# Helpers
# ---------------------------

def _get_json(url: str, params: dict | None = None, timeout: int = 30) -> dict:
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _first(records: list) -> Optional[dict]:
    return records[0] if records else None

def _try_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


# ---------------------------
# 1) Commune metadata by INSEE
# ---------------------------

def fetch_commune_meta(insee: str) -> Dict[str, Any]:
    # geo.api.gouv.fr supports direct access: /communes/{code}
    url = f"https://geo.api.gouv.fr/communes/{insee}"
    params = {"fields": "code,nom,codeDepartement,codeRegion,population", "format": "json"}
    data = _get_json(url, params=params)
    return {
        "insee": data.get("code"),
        "nom": data.get("nom"),
        "code_departement": data.get("codeDepartement"),
        "code_region": data.get("codeRegion"),
        # population here is not always the legal population millésimée you may want;
        # we fetch legal population separately below.
        "population_geoapi": data.get("population"),
    }


# ---------------------------
# 2) Legal population (Opendatasoft public mirror)
# ---------------------------

def fetch_legal_population(insee: str, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Pull legal population from a public Opendatasoft dataset.
    If year is None, tries to get the latest available record for the commune.
    """
    url = "https://public.opendatasoft.com/api/records/1.0/search/"
    # This dataset name can evolve. The script auto-discovers fields and sorts by year if present.
    dataset = "demographyref-france-pop-legale-commune-arrondissement-municipal-millesime"

    # First: fetch one record to inspect schema
    schema_probe = _get_json(url, params={"dataset": dataset, "q": "", "rows": 1})
    rec0 = _first(schema_probe.get("records", []))
    if not rec0:
        return {"ok": False, "error": "Population dataset returned no records (probe)."}
    fields0 = rec0["fields"].keys()

    # Guess field names
    # common possibilities
    insee_fields = ["code_insee_commune", "insee_com", "code_commune_insee", "code_insee"]
    year_fields = ["millesime", "annee", "year"]
    pop_fields = ["pmun", "population", "pop_mun", "population_municipale", "poptot"]

    def pick(candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in fields0:
                return c
        return None

    f_insee = pick(insee_fields)
    f_year = pick(year_fields)
    f_pop = pick(pop_fields)

    if not f_insee or not f_pop:
        return {
            "ok": False,
            "error": f"Could not auto-detect INSEE/population fields in {dataset}. Found fields: {sorted(fields0)[:30]}..."
        }

    params = {
        "dataset": dataset,
        "q": "",
        "rows": 50,
        f"refine.{f_insee}": insee,
    }
    data = _get_json(url, params=params)
    recs = data.get("records", [])

    if not recs:
        return {"ok": False, "error": f"No legal population record found for INSEE={insee} in {dataset}."}

    # Choose record: exact year if provided, else latest by year field if exists, else first.
    chosen = None
    if year is not None and f_year:
        for r in recs:
            if str(r["fields"].get(f_year)) == str(year):
                chosen = r
                break

    if chosen is None and f_year:
        # pick max year
        def year_key(r):
            try:
                return int(str(r["fields"].get(f_year)))
            except Exception:
                return -1
        chosen = sorted(recs, key=year_key, reverse=True)[0]
    if chosen is None:
        chosen = recs[0]

    pop_val = chosen["fields"].get(f_pop)
    pop_num = None
    if isinstance(pop_val, (int, float)):
        pop_num = int(pop_val)
    else:
        fv = _try_float(pop_val)
        pop_num = int(fv) if fv is not None else None

    return {
        "ok": True,
        "dataset": dataset,
        "field_insee": f_insee,
        "field_year": f_year,
        "field_population": f_pop,
        "year_used": chosen["fields"].get(f_year) if f_year else None,
        "population": pop_num,
    }


# ---------------------------
# 3) Enedis electricity consumption (annual) + kWh/hab
# ---------------------------

def fetch_enedis_electricity(insee: str, year: int, sector: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch annual electricity consumption from Enedis Opendatasoft and return kWh.
    sector: None (all) or one sector label if available in the dataset.
    """
    url = "https://opendata.enedis.fr/api/records/1.0/search/"
    dataset = "consommation-electrique-par-secteur-dactivite-commune"

    # Probe schema
    probe = _get_json(url, params={"dataset": dataset, "q": "", "rows": 1})
    rec0 = _first(probe.get("records", []))
    if not rec0:
        return {"ok": False, "error": "Enedis dataset returned no records (probe)."}
    fields0 = rec0["fields"].keys()

    # Guess field names
    insee_fields = ["code_insee_commune", "insee_com", "code_commune_insee", "code_insee"]
    year_fields = ["annee", "millesime", "year"]
    sector_fields = ["secteur_activite", "secteur", "libelle_secteur", "secteur_dactivite"]
    # consumption fields often MWh; may be conso_mwh, consommation_mwh, etc.
    conso_fields = ["conso_mwh", "consommation_mwh", "conso", "consommation"]

    def pick(candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in fields0:
                return c
        return None

    f_insee = pick(insee_fields)
    f_year = pick(year_fields)
    f_sector = pick(sector_fields)
    f_conso = pick(conso_fields)

    if not f_insee or not f_year or not f_conso:
        return {
            "ok": False,
            "error": f"Could not auto-detect needed fields in {dataset}. Found fields: {sorted(fields0)[:40]}..."
        }

    params = {
        "dataset": dataset,
        "q": "",
        "rows": 1000,
        f"refine.{f_insee}": insee,
        f"refine.{f_year}": str(year),
    }
    if sector and f_sector:
        params[f"refine.{f_sector}"] = sector

    data = _get_json(url, params=params)
    recs = data.get("records", [])
    if not recs:
        return {"ok": False, "error": f"No Enedis electricity records for INSEE={insee}, year={year}, sector={sector}."}

    # Sum consumption; assume unit is MWh unless field clearly says kWh (rare)
    total = 0.0
    for r in recs:
        v = r["fields"].get(f_conso)
        fv = _try_float(v)
        if fv is not None:
            total += fv

    # Heuristic: treat as MWh if values are not enormous;
    # Enedis commonly uses MWh. Convert to kWh.
    total_mwh = total
    total_kwh = total_mwh * 1000.0

    return {
        "ok": True,
        "dataset": dataset,
        "field_insee": f_insee,
        "field_year": f_year,
        "field_sector": f_sector,
        "field_consumption": f_conso,
        "year": year,
        "sector": sector,
        "consumption_mwh": total_mwh,
        "consumption_kwh": total_kwh,
        "records_used": len(recs),
    }


# ---------------------------
# 4) Air quality index (ATMO) today via WFS
# ---------------------------

def fetch_atmo_index_today(insee: str, date_utc: Optional[dt.date] = None) -> Dict[str, Any]:
    """
    Query Atmo France GeoServer WFS for today's ATMO index at commune level.
    The biggest pitfall is field names; we probe and then query with detected names.
    """
    if date_utc is None:
        date_utc = dt.datetime.utcnow().date()

    base = "https://data.atmo-france.org/geoserver/ind/ows"
    type_name = "ind:ind_atmo"

    # Probe
    probe = _get_json(base, params={
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": type_name,
        "outputFormat": "application/json",
        "count": 1,
    })
    feats = probe.get("features", [])
    if not feats:
        return {"ok": False, "error": "Atmo WFS probe returned no features."}

    props0 = feats[0].get("properties", {})
    keys0 = set(props0.keys())

    # Likely fields
    insee_fields = ["code_zone", "insee_com", "code_insee_commune", "code_insee"]
    date_fields = ["date_ech", "date", "date_validite", "date_obs"]
    index_fields = ["ind", "indice", "indice_atmo", "valeur", "value", "ind_atmo"]

    def pick(candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in keys0:
                return c
        return None

    f_insee = pick(insee_fields)
    f_date = pick(date_fields)
    f_idx = pick(index_fields)

    if not f_insee or not f_date:
        return {
            "ok": False,
            "error": f"Could not detect INSEE/date fields in Atmo WFS. Found: {sorted(list(keys0))[:40]}..."
        }

    # Build day window in UTC
    start = dt.datetime(date_utc.year, date_utc.month, date_utc.day, 0, 0, 0)
    end = start + dt.timedelta(days=1)

    # CQL filter
    # Note: date format depends; GeoServer usually accepts ISO timestamps.
    cql = f"{f_insee}='{insee}' AND {f_date} >= '{start.isoformat()}Z' AND {f_date} < '{end.isoformat()}Z'"

    data = _get_json(base, params={
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": type_name,
        "outputFormat": "application/json",
        "CQL_FILTER": cql,
        "count": 50,
    })

    feats = data.get("features", [])
    if not feats:
        return {
            "ok": False,
            "dataset": type_name,
            "field_insee": f_insee,
            "field_date": f_date,
            "field_index_guess": f_idx,
            "error": f"No ATMO features found for INSEE={insee} on {date_utc.isoformat()} (field names ok, data may not be published yet)."
        }

    # If multiple, pick latest by date field
    def parse_dt(x):
        try:
            # accept '2026-01-20T...' etc.
            return dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        except Exception:
            return dt.datetime.min

    feats_sorted = sorted(feats, key=lambda f: parse_dt(f["properties"].get(f_date)), reverse=True)
    best = feats_sorted[0]["properties"]

    idx_val = best.get(f_idx) if f_idx else None

    return {
        "ok": True,
        "dataset": type_name,
        "field_insee": f_insee,
        "field_date": f_date,
        "field_index": f_idx,
        "date_used": best.get(f_date),
        "index_value": idx_val,
        "properties": best,  # keep full payload for debugging / extra fields
        "features_used": len(feats),
    }


# ---------------------------
# Orchestrator
# ---------------------------

def ecological_profile(insee: str, energy_year: int, energy_sector: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"insee": insee, "generated_at_utc": dt.datetime.utcnow().isoformat() + "Z"}

    # Commune meta
    out["commune"] = fetch_commune_meta(insee)

    # Population
    pop = fetch_legal_population(insee, year=energy_year)
    out["population_legal"] = pop

    # Electricity
    elec = fetch_enedis_electricity(insee, year=energy_year, sector=energy_sector)
    out["electricity"] = elec

    # kWh/hab
    if pop.get("ok") and elec.get("ok") and pop.get("population"):
        out["kwh_per_inhabitant"] = elec["consumption_kwh"] / float(pop["population"])
    else:
        out["kwh_per_inhabitant"] = None

    # Air quality today
    out["air_quality_today"] = fetch_atmo_index_today(insee)

    return out


# ---------------------------
# CLI
# ---------------------------

if __name__ == "__main__":
    # Example: Rennes 35238
    insee = sys.argv[1] if len(sys.argv) > 1 else "35238"
    year = int(sys.argv[2]) if len(sys.argv) > 2 else (dt.datetime.utcnow().year - 1)
    sector = sys.argv[3] if len(sys.argv) > 3 else None

    result = ecological_profile(insee, energy_year=year, energy_sector=sector)
    print(json.dumps(result, ensure_ascii=False, indent=2))
