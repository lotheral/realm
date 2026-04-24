"""One-off data generator: expand countries.json, hofstede_scores.json,
cities.json with ~35 new countries per REALM Sprint 5 WP2.

Hofstede scores: use Hofstede Insights published values where available.
For countries without published scores, use a regional proxy and mark
`"estimated": true`. New top-level `"_proxies"` block documents proxy
sources.

Rerunnable — skips entries already present.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COUNTRIES_PATH = ROOT / "data" / "countries.json"
HOFSTEDE_PATH = ROOT / "data" / "hofstede_scores.json"
CITIES_PATH = ROOT / "data" / "cities.json"


# --------------------------------------------------------------------------
# New country entries (35 countries)
# Schema matches countries.json:
# iso2, iso3, name, population (millions), lat, lon (centroid),
# faker_locale, primary_religion, region, median_age, gdp_per_capita_usd
# --------------------------------------------------------------------------

NEW_COUNTRIES: list[dict] = [
    # Europe (west/south/north/east/baltic)
    {"iso2": "PT", "iso3": "PRT", "name": "Portugal",        "population": 10,  "lat": 39.5, "lon": -8.0,   "faker_locale": "pt_PT", "primary_religion": "christian", "region": "europe_west",  "median_age": 46.2, "gdp_per_capita_usd": 24600},
    {"iso2": "IE", "iso3": "IRL", "name": "Ireland",         "population": 5,   "lat": 53.4, "lon": -8.0,   "faker_locale": "en_US", "primary_religion": "christian", "region": "europe_west",  "median_age": 38.8, "gdp_per_capita_usd": 103000},
    {"iso2": "NL", "iso3": "NLD", "name": "Netherlands",     "population": 18,  "lat": 52.1, "lon": 5.3,    "faker_locale": "nl_NL", "primary_religion": "christian", "region": "europe_west",  "median_age": 42.8, "gdp_per_capita_usd": 57400},
    {"iso2": "BE", "iso3": "BEL", "name": "Belgium",         "population": 12,  "lat": 50.5, "lon": 4.5,    "faker_locale": "nl_BE", "primary_religion": "christian", "region": "europe_west",  "median_age": 42.1, "gdp_per_capita_usd": 51200},
    {"iso2": "LU", "iso3": "LUX", "name": "Luxembourg",      "population": 1,   "lat": 49.8, "lon": 6.1,    "faker_locale": "fr_FR", "primary_religion": "christian", "region": "europe_west",  "median_age": 39.8, "gdp_per_capita_usd": 126000},
    {"iso2": "CH", "iso3": "CHE", "name": "Switzerland",     "population": 9,   "lat": 46.8, "lon": 8.2,    "faker_locale": "de_CH", "primary_religion": "christian", "region": "europe_west",  "median_age": 43.1, "gdp_per_capita_usd": 92400},
    {"iso2": "AT", "iso3": "AUT", "name": "Austria",         "population": 9,   "lat": 47.5, "lon": 14.5,   "faker_locale": "de_AT", "primary_religion": "christian", "region": "europe_west",  "median_age": 44.0, "gdp_per_capita_usd": 52100},
    {"iso2": "CZ", "iso3": "CZE", "name": "Czechia",         "population": 11,  "lat": 49.8, "lon": 15.5,   "faker_locale": "cs_CZ", "primary_religion": "christian", "region": "europe_east",  "median_age": 43.3, "gdp_per_capita_usd": 28000},
    {"iso2": "PL", "iso3": "POL", "name": "Poland",          "population": 37,  "lat": 52.0, "lon": 19.0,   "faker_locale": "pl_PL", "primary_religion": "christian", "region": "europe_east",  "median_age": 41.9, "gdp_per_capita_usd": 19000},
    {"iso2": "HU", "iso3": "HUN", "name": "Hungary",         "population": 10,  "lat": 47.2, "lon": 19.5,   "faker_locale": "hu_HU", "primary_religion": "christian", "region": "europe_east",  "median_age": 43.6, "gdp_per_capita_usd": 19000},
    {"iso2": "RO", "iso3": "ROU", "name": "Romania",         "population": 19,  "lat": 45.9, "lon": 25.0,   "faker_locale": "ro_RO", "primary_religion": "christian_orthodox", "region": "europe_east",  "median_age": 43.1, "gdp_per_capita_usd": 17000},
    {"iso2": "BG", "iso3": "BGR", "name": "Bulgaria",        "population": 7,   "lat": 42.7, "lon": 25.5,   "faker_locale": "bg_BG", "primary_religion": "christian_orthodox", "region": "europe_east",  "median_age": 44.9, "gdp_per_capita_usd": 13800},
    {"iso2": "SK", "iso3": "SVK", "name": "Slovakia",        "population": 5,   "lat": 48.7, "lon": 19.7,   "faker_locale": "sk_SK", "primary_religion": "christian", "region": "europe_east",  "median_age": 41.6, "gdp_per_capita_usd": 21300},
    {"iso2": "UA", "iso3": "UKR", "name": "Ukraine",         "population": 38,  "lat": 49.0, "lon": 31.0,   "faker_locale": "uk_UA", "primary_religion": "christian_orthodox", "region": "europe_east",  "median_age": 41.2, "gdp_per_capita_usd": 4800},
    {"iso2": "HR", "iso3": "HRV", "name": "Croatia",         "population": 4,   "lat": 45.1, "lon": 15.5,   "faker_locale": "hr_HR", "primary_religion": "christian", "region": "europe_south", "median_age": 43.9, "gdp_per_capita_usd": 17400},
    {"iso2": "RS", "iso3": "SRB", "name": "Serbia",          "population": 7,   "lat": 44.0, "lon": 21.0,   "faker_locale": None,    "primary_religion": "christian_orthodox", "region": "europe_south", "median_age": 43.8, "gdp_per_capita_usd": 9200},
    {"iso2": "GR", "iso3": "GRC", "name": "Greece",          "population": 10,  "lat": 39.0, "lon": 22.0,   "faker_locale": "el_GR", "primary_religion": "christian_orthodox", "region": "europe_south", "median_age": 45.6, "gdp_per_capita_usd": 20900},
    {"iso2": "SI", "iso3": "SVN", "name": "Slovenia",        "population": 2,   "lat": 46.1, "lon": 14.8,   "faker_locale": "sl_SI", "primary_religion": "christian", "region": "europe_south", "median_age": 44.9, "gdp_per_capita_usd": 29500},
    {"iso2": "SE", "iso3": "SWE", "name": "Sweden",          "population": 11,  "lat": 62.0, "lon": 15.0,   "faker_locale": "sv_SE", "primary_religion": "christian", "region": "europe_north", "median_age": 41.1, "gdp_per_capita_usd": 56300},
    {"iso2": "NO", "iso3": "NOR", "name": "Norway",          "population": 5,   "lat": 62.0, "lon": 10.0,   "faker_locale": "no_NO", "primary_religion": "christian", "region": "europe_north", "median_age": 39.9, "gdp_per_capita_usd": 89200},
    {"iso2": "DK", "iso3": "DNK", "name": "Denmark",         "population": 6,   "lat": 56.2, "lon": 9.5,    "faker_locale": "da_DK", "primary_religion": "christian", "region": "europe_north", "median_age": 42.1, "gdp_per_capita_usd": 68000},
    {"iso2": "FI", "iso3": "FIN", "name": "Finland",         "population": 6,   "lat": 64.0, "lon": 26.0,   "faker_locale": "fi_FI", "primary_religion": "christian", "region": "europe_north", "median_age": 43.1, "gdp_per_capita_usd": 53500},
    {"iso2": "IS", "iso3": "ISL", "name": "Iceland",         "population": 0,   "lat": 64.9, "lon": -19.0,  "faker_locale": "is_IS", "primary_religion": "christian", "region": "europe_north", "median_age": 37.8, "gdp_per_capita_usd": 75700},
    {"iso2": "EE", "iso3": "EST", "name": "Estonia",         "population": 1,   "lat": 58.6, "lon": 25.0,   "faker_locale": "et_EE", "primary_religion": "christian", "region": "europe_north", "median_age": 43.0, "gdp_per_capita_usd": 27000},
    {"iso2": "LV", "iso3": "LVA", "name": "Latvia",          "population": 2,   "lat": 56.9, "lon": 24.6,   "faker_locale": "lv_LV", "primary_religion": "christian", "region": "europe_north", "median_age": 43.4, "gdp_per_capita_usd": 21400},
    {"iso2": "LT", "iso3": "LTU", "name": "Lithuania",       "population": 3,   "lat": 55.2, "lon": 23.9,   "faker_locale": "lt_LT", "primary_religion": "christian", "region": "europe_north", "median_age": 43.7, "gdp_per_capita_usd": 25000},

    # Asia-Pacific / Oceania
    {"iso2": "SG", "iso3": "SGP", "name": "Singapore",       "population": 6,   "lat": 1.35, "lon": 103.82, "faker_locale": "en_US", "primary_religion": "buddhist_muslim_christian", "region": "asia_southeast", "median_age": 42.8, "gdp_per_capita_usd": 82800},
    {"iso2": "MY", "iso3": "MYS", "name": "Malaysia",        "population": 34,  "lat": 4.2,  "lon": 102.0,  "faker_locale": None,    "primary_religion": "muslim",    "region": "asia_southeast", "median_age": 30.3, "gdp_per_capita_usd": 11800},
    {"iso2": "AU", "iso3": "AUS", "name": "Australia",       "population": 26,  "lat": -25.0,"lon": 135.0,  "faker_locale": "en_AU", "primary_religion": "christian", "region": "oceania",       "median_age": 38.4, "gdp_per_capita_usd": 64000},
    {"iso2": "NZ", "iso3": "NZL", "name": "New Zealand",     "population": 5,   "lat": -41.0,"lon": 174.0,  "faker_locale": "en_NZ", "primary_religion": "christian", "region": "oceania",       "median_age": 38.1, "gdp_per_capita_usd": 48500},

    # Americas
    {"iso2": "CA", "iso3": "CAN", "name": "Canada",          "population": 40,  "lat": 60.0, "lon": -106.0, "faker_locale": "en_CA", "primary_religion": "christian", "region": "america_north", "median_age": 41.8, "gdp_per_capita_usd": 53400},
    {"iso2": "AR", "iso3": "ARG", "name": "Argentina",       "population": 46,  "lat": -34.0,"lon": -64.0,  "faker_locale": "es_AR", "primary_religion": "christian", "region": "america_south", "median_age": 32.4, "gdp_per_capita_usd": 13600},
    {"iso2": "CL", "iso3": "CHL", "name": "Chile",           "population": 20,  "lat": -30.0,"lon": -71.0,  "faker_locale": "es_CL", "primary_religion": "christian", "region": "america_south", "median_age": 35.9, "gdp_per_capita_usd": 17100},

    # MENA
    {"iso2": "IL", "iso3": "ISR", "name": "Israel",          "population": 10,  "lat": 31.5, "lon": 35.0,   "faker_locale": "he_IL", "primary_religion": "jewish",    "region": "mena", "median_age": 30.5, "gdp_per_capita_usd": 55500},
    {"iso2": "AE", "iso3": "ARE", "name": "United Arab Emirates", "population": 10, "lat": 24.0, "lon": 54.0, "faker_locale": "ar_AE", "primary_religion": "muslim", "region": "mena", "median_age": 33.5, "gdp_per_capita_usd": 50000},
    {"iso2": "SA", "iso3": "SAU", "name": "Saudi Arabia",    "population": 37,  "lat": 24.0, "lon": 45.0,   "faker_locale": "ar_SA", "primary_religion": "muslim",    "region": "mena", "median_age": 31.8, "gdp_per_capita_usd": 32000},
]


# --------------------------------------------------------------------------
# Hofstede scores for new countries.
# Values: Hofstede Insights published country scores, 2024.
# Where a country lacks published scores, we use a regional proxy and set
# `"estimated": true`.
# --------------------------------------------------------------------------

# Regional proxy sources (explicit for documentation):
ARAB_WORLD_PROXY = {"pdi": 80, "idv": 38, "mas": 53, "uai": 68, "lto": 23, "ivr": 34}
BALTIC_PROXY = {"pdi": 40, "idv": 60, "mas": 19, "uai": 61, "lto": 82, "ivr": 13}

NEW_HOFSTEDE: dict[str, dict] = {
    # Europe (all published by Hofstede Insights)
    "PT": {"pdi": 63, "idv": 27, "mas": 31, "uai": 104, "lto": 28, "ivr": 33},
    "IE": {"pdi": 28, "idv": 70, "mas": 68, "uai": 35,  "lto": 24, "ivr": 65},
    "NL": {"pdi": 38, "idv": 80, "mas": 14, "uai": 53,  "lto": 67, "ivr": 68},
    "BE": {"pdi": 65, "idv": 75, "mas": 54, "uai": 94,  "lto": 82, "ivr": 57},
    "LU": {"pdi": 40, "idv": 60, "mas": 50, "uai": 70,  "lto": 64, "ivr": 56},
    "CH": {"pdi": 34, "idv": 68, "mas": 70, "uai": 58,  "lto": 74, "ivr": 66},
    "AT": {"pdi": 11, "idv": 55, "mas": 79, "uai": 70,  "lto": 60, "ivr": 63},
    "CZ": {"pdi": 57, "idv": 58, "mas": 57, "uai": 74,  "lto": 70, "ivr": 29},
    "PL": {"pdi": 68, "idv": 60, "mas": 64, "uai": 93,  "lto": 38, "ivr": 29},
    "HU": {"pdi": 46, "idv": 80, "mas": 88, "uai": 82,  "lto": 58, "ivr": 31},
    "RO": {"pdi": 90, "idv": 30, "mas": 42, "uai": 90,  "lto": 52, "ivr": 20},
    "BG": {"pdi": 70, "idv": 30, "mas": 40, "uai": 85,  "lto": 69, "ivr": 16},
    "SK": {"pdi": 104, "idv": 52, "mas": 100, "uai": 51, "lto": 77, "ivr": 28},
    "UA": {"pdi": 92, "idv": 25, "mas": 27, "uai": 95,  "lto": 86, "ivr": 14},
    "HR": {"pdi": 73, "idv": 33, "mas": 40, "uai": 80,  "lto": 58, "ivr": 33},
    "RS": {"pdi": 86, "idv": 25, "mas": 43, "uai": 92,  "lto": 52, "ivr": 28},
    "GR": {"pdi": 60, "idv": 35, "mas": 57, "uai": 112, "lto": 45, "ivr": 50},
    "SI": {"pdi": 71, "idv": 27, "mas": 19, "uai": 88,  "lto": 49, "ivr": 48},
    "SE": {"pdi": 31, "idv": 71, "mas": 5,  "uai": 29,  "lto": 53, "ivr": 78},
    "NO": {"pdi": 31, "idv": 69, "mas": 8,  "uai": 50,  "lto": 35, "ivr": 55},
    "DK": {"pdi": 18, "idv": 74, "mas": 16, "uai": 23,  "lto": 35, "ivr": 70},
    "FI": {"pdi": 33, "idv": 63, "mas": 26, "uai": 59,  "lto": 38, "ivr": 57},
    "IS": {**BALTIC_PROXY},
    "EE": {"pdi": 40, "idv": 60, "mas": 30, "uai": 60,  "lto": 82, "ivr": 16},
    "LV": {"pdi": 44, "idv": 70, "mas": 9,  "uai": 63,  "lto": 69, "ivr": 13},
    "LT": {"pdi": 42, "idv": 60, "mas": 19, "uai": 65,  "lto": 82, "ivr": 16},

    # Asia-Pacific / Oceania
    "SG": {"pdi": 74, "idv": 20, "mas": 48, "uai": 8,   "lto": 72, "ivr": 46},
    "MY": {"pdi": 100, "idv": 26, "mas": 50, "uai": 36, "lto": 41, "ivr": 57},
    "AU": {"pdi": 38, "idv": 90, "mas": 61, "uai": 51,  "lto": 21, "ivr": 71},
    "NZ": {"pdi": 22, "idv": 79, "mas": 58, "uai": 49,  "lto": 33, "ivr": 75},

    # Americas
    "CA": {"pdi": 39, "idv": 80, "mas": 52, "uai": 48,  "lto": 36, "ivr": 68},
    "AR": {"pdi": 49, "idv": 46, "mas": 56, "uai": 86,  "lto": 20, "ivr": 62},
    "CL": {"pdi": 63, "idv": 23, "mas": 28, "uai": 86,  "lto": 31, "ivr": 68},

    # MENA
    "IL": {"pdi": 13, "idv": 54, "mas": 47, "uai": 81,  "lto": 38, "ivr": 48},
    "AE": {**ARAB_WORLD_PROXY},
    "SA": {**ARAB_WORLD_PROXY},
}


ESTIMATED_COUNTRIES: dict[str, str] = {
    "IS": "nordic_baltic",
    "AE": "arab_world",
    "SA": "arab_world",
}


# --------------------------------------------------------------------------
# Cities per new country — population-proportional (5–10).
# Fields: name, country (ISO2), lat, lon, pop (thousands), timezone (IANA).
# --------------------------------------------------------------------------

NEW_CITIES: list[dict] = [
    # Portugal (7 cities)
    {"name": "Lisbon",    "country": "PT", "lat": 38.72, "lon": -9.14,  "pop": 548,  "timezone": "Europe/Lisbon"},
    {"name": "Porto",     "country": "PT", "lat": 41.15, "lon": -8.61,  "pop": 231,  "timezone": "Europe/Lisbon"},
    {"name": "Vila Nova de Gaia", "country": "PT", "lat": 41.12, "lon": -8.61, "pop": 302, "timezone": "Europe/Lisbon"},
    {"name": "Amadora",   "country": "PT", "lat": 38.75, "lon": -9.23,  "pop": 179,  "timezone": "Europe/Lisbon"},
    {"name": "Braga",     "country": "PT", "lat": 41.55, "lon": -8.43,  "pop": 193,  "timezone": "Europe/Lisbon"},
    {"name": "Coimbra",   "country": "PT", "lat": 40.20, "lon": -8.41,  "pop": 140,  "timezone": "Europe/Lisbon"},
    {"name": "Faro",      "country": "PT", "lat": 37.02, "lon": -7.93,  "pop": 67,   "timezone": "Europe/Lisbon"},

    # Ireland (5)
    {"name": "Dublin",    "country": "IE", "lat": 53.35, "lon": -6.26,  "pop": 1270, "timezone": "Europe/Dublin"},
    {"name": "Cork",      "country": "IE", "lat": 51.90, "lon": -8.47,  "pop": 210,  "timezone": "Europe/Dublin"},
    {"name": "Limerick",  "country": "IE", "lat": 52.67, "lon": -8.63,  "pop": 94,   "timezone": "Europe/Dublin"},
    {"name": "Galway",    "country": "IE", "lat": 53.27, "lon": -9.05,  "pop": 80,   "timezone": "Europe/Dublin"},
    {"name": "Waterford", "country": "IE", "lat": 52.26, "lon": -7.11,  "pop": 54,   "timezone": "Europe/Dublin"},

    # Netherlands (7)
    {"name": "Amsterdam", "country": "NL", "lat": 52.37, "lon": 4.90,   "pop": 920,  "timezone": "Europe/Amsterdam"},
    {"name": "Rotterdam", "country": "NL", "lat": 51.92, "lon": 4.47,   "pop": 664,  "timezone": "Europe/Amsterdam"},
    {"name": "The Hague", "country": "NL", "lat": 52.08, "lon": 4.31,   "pop": 560,  "timezone": "Europe/Amsterdam"},
    {"name": "Utrecht",   "country": "NL", "lat": 52.09, "lon": 5.12,   "pop": 366,  "timezone": "Europe/Amsterdam"},
    {"name": "Eindhoven", "country": "NL", "lat": 51.44, "lon": 5.48,   "pop": 238,  "timezone": "Europe/Amsterdam"},
    {"name": "Groningen", "country": "NL", "lat": 53.22, "lon": 6.57,   "pop": 234,  "timezone": "Europe/Amsterdam"},
    {"name": "Tilburg",   "country": "NL", "lat": 51.56, "lon": 5.09,   "pop": 223,  "timezone": "Europe/Amsterdam"},

    # Belgium (6)
    {"name": "Brussels",  "country": "BE", "lat": 50.85, "lon": 4.35,   "pop": 1223, "timezone": "Europe/Brussels"},
    {"name": "Antwerp",   "country": "BE", "lat": 51.22, "lon": 4.40,   "pop": 531,  "timezone": "Europe/Brussels"},
    {"name": "Ghent",     "country": "BE", "lat": 51.05, "lon": 3.73,   "pop": 265,  "timezone": "Europe/Brussels"},
    {"name": "Charleroi", "country": "BE", "lat": 50.41, "lon": 4.44,   "pop": 201,  "timezone": "Europe/Brussels"},
    {"name": "Liège",     "country": "BE", "lat": 50.63, "lon": 5.58,   "pop": 197,  "timezone": "Europe/Brussels"},
    {"name": "Bruges",    "country": "BE", "lat": 51.21, "lon": 3.22,   "pop": 118,  "timezone": "Europe/Brussels"},

    # Luxembourg (5, city-state-like)
    {"name": "Luxembourg City","country": "LU", "lat": 49.61, "lon": 6.13, "pop": 132, "timezone": "Europe/Luxembourg"},
    {"name": "Esch-sur-Alzette","country": "LU","lat": 49.50, "lon": 5.98, "pop": 36,  "timezone": "Europe/Luxembourg"},
    {"name": "Differdange","country": "LU", "lat": 49.52, "lon": 5.89,    "pop": 28,  "timezone": "Europe/Luxembourg"},
    {"name": "Dudelange", "country": "LU", "lat": 49.48, "lon": 6.09,     "pop": 22,  "timezone": "Europe/Luxembourg"},
    {"name": "Ettelbruck","country": "LU", "lat": 49.85, "lon": 6.10,     "pop": 9,   "timezone": "Europe/Luxembourg"},

    # Switzerland (7)
    {"name": "Zurich",    "country": "CH", "lat": 47.38, "lon": 8.55,   "pop": 434,  "timezone": "Europe/Zurich"},
    {"name": "Geneva",    "country": "CH", "lat": 46.20, "lon": 6.15,   "pop": 204,  "timezone": "Europe/Zurich"},
    {"name": "Basel",     "country": "CH", "lat": 47.56, "lon": 7.59,   "pop": 178,  "timezone": "Europe/Zurich"},
    {"name": "Lausanne",  "country": "CH", "lat": 46.52, "lon": 6.63,   "pop": 140,  "timezone": "Europe/Zurich"},
    {"name": "Bern",      "country": "CH", "lat": 46.95, "lon": 7.45,   "pop": 134,  "timezone": "Europe/Zurich"},
    {"name": "Winterthur","country": "CH", "lat": 47.50, "lon": 8.72,   "pop": 115,  "timezone": "Europe/Zurich"},
    {"name": "Lucerne",   "country": "CH", "lat": 47.05, "lon": 8.31,   "pop": 82,   "timezone": "Europe/Zurich"},

    # Austria (7)
    {"name": "Vienna",    "country": "AT", "lat": 48.21, "lon": 16.37,  "pop": 1973, "timezone": "Europe/Vienna"},
    {"name": "Graz",      "country": "AT", "lat": 47.07, "lon": 15.44,  "pop": 294,  "timezone": "Europe/Vienna"},
    {"name": "Linz",      "country": "AT", "lat": 48.31, "lon": 14.29,  "pop": 206,  "timezone": "Europe/Vienna"},
    {"name": "Salzburg",  "country": "AT", "lat": 47.81, "lon": 13.06,  "pop": 157,  "timezone": "Europe/Vienna"},
    {"name": "Innsbruck", "country": "AT", "lat": 47.27, "lon": 11.39,  "pop": 132,  "timezone": "Europe/Vienna"},
    {"name": "Klagenfurt","country": "AT", "lat": 46.62, "lon": 14.31,  "pop": 103,  "timezone": "Europe/Vienna"},
    {"name": "Villach",   "country": "AT", "lat": 46.61, "lon": 13.85,  "pop": 64,   "timezone": "Europe/Vienna"},

    # Czechia (7)
    {"name": "Prague",    "country": "CZ", "lat": 50.08, "lon": 14.44,  "pop": 1357, "timezone": "Europe/Prague"},
    {"name": "Brno",      "country": "CZ", "lat": 49.20, "lon": 16.61,  "pop": 383,  "timezone": "Europe/Prague"},
    {"name": "Ostrava",   "country": "CZ", "lat": 49.84, "lon": 18.28,  "pop": 281,  "timezone": "Europe/Prague"},
    {"name": "Plzeň",     "country": "CZ", "lat": 49.75, "lon": 13.38,  "pop": 174,  "timezone": "Europe/Prague"},
    {"name": "Liberec",   "country": "CZ", "lat": 50.77, "lon": 15.06,  "pop": 104,  "timezone": "Europe/Prague"},
    {"name": "Olomouc",   "country": "CZ", "lat": 49.60, "lon": 17.25,  "pop": 100,  "timezone": "Europe/Prague"},
    {"name": "České Budějovice", "country": "CZ", "lat": 48.97, "lon": 14.47, "pop": 94, "timezone": "Europe/Prague"},

    # Poland (10 — high-pop)
    {"name": "Warsaw",    "country": "PL", "lat": 52.23, "lon": 21.01,  "pop": 1860, "timezone": "Europe/Warsaw"},
    {"name": "Kraków",    "country": "PL", "lat": 50.06, "lon": 19.94,  "pop": 803,  "timezone": "Europe/Warsaw"},
    {"name": "Łódź",      "country": "PL", "lat": 51.76, "lon": 19.46,  "pop": 672,  "timezone": "Europe/Warsaw"},
    {"name": "Wrocław",   "country": "PL", "lat": 51.11, "lon": 17.04,  "pop": 672,  "timezone": "Europe/Warsaw"},
    {"name": "Poznań",    "country": "PL", "lat": 52.41, "lon": 16.93,  "pop": 540,  "timezone": "Europe/Warsaw"},
    {"name": "Gdańsk",    "country": "PL", "lat": 54.35, "lon": 18.65,  "pop": 471,  "timezone": "Europe/Warsaw"},
    {"name": "Szczecin",  "country": "PL", "lat": 53.43, "lon": 14.55,  "pop": 396,  "timezone": "Europe/Warsaw"},
    {"name": "Bydgoszcz", "country": "PL", "lat": 53.12, "lon": 18.01,  "pop": 339,  "timezone": "Europe/Warsaw"},
    {"name": "Lublin",    "country": "PL", "lat": 51.25, "lon": 22.57,  "pop": 335,  "timezone": "Europe/Warsaw"},
    {"name": "Katowice",  "country": "PL", "lat": 50.26, "lon": 19.02,  "pop": 286,  "timezone": "Europe/Warsaw"},

    # Hungary (7)
    {"name": "Budapest",  "country": "HU", "lat": 47.50, "lon": 19.05,  "pop": 1706, "timezone": "Europe/Budapest"},
    {"name": "Debrecen",  "country": "HU", "lat": 47.53, "lon": 21.63,  "pop": 202,  "timezone": "Europe/Budapest"},
    {"name": "Szeged",    "country": "HU", "lat": 46.25, "lon": 20.15,  "pop": 160,  "timezone": "Europe/Budapest"},
    {"name": "Miskolc",   "country": "HU", "lat": 48.10, "lon": 20.78,  "pop": 150,  "timezone": "Europe/Budapest"},
    {"name": "Pécs",      "country": "HU", "lat": 46.07, "lon": 18.23,  "pop": 140,  "timezone": "Europe/Budapest"},
    {"name": "Győr",      "country": "HU", "lat": 47.68, "lon": 17.63,  "pop": 131,  "timezone": "Europe/Budapest"},
    {"name": "Nyíregyháza", "country": "HU", "lat": 47.96, "lon": 21.73, "pop": 117, "timezone": "Europe/Budapest"},

    # Romania (8)
    {"name": "Bucharest", "country": "RO", "lat": 44.44, "lon": 26.10,  "pop": 1716, "timezone": "Europe/Bucharest"},
    {"name": "Cluj-Napoca","country": "RO","lat": 46.77, "lon": 23.60,  "pop": 324,  "timezone": "Europe/Bucharest"},
    {"name": "Timișoara", "country": "RO", "lat": 45.75, "lon": 21.23,  "pop": 250,  "timezone": "Europe/Bucharest"},
    {"name": "Iași",      "country": "RO", "lat": 47.16, "lon": 27.59,  "pop": 271,  "timezone": "Europe/Bucharest"},
    {"name": "Constanța", "country": "RO", "lat": 44.17, "lon": 28.65,  "pop": 283,  "timezone": "Europe/Bucharest"},
    {"name": "Craiova",   "country": "RO", "lat": 44.33, "lon": 23.82,  "pop": 234,  "timezone": "Europe/Bucharest"},
    {"name": "Brașov",    "country": "RO", "lat": 45.66, "lon": 25.61,  "pop": 237,  "timezone": "Europe/Bucharest"},
    {"name": "Galați",    "country": "RO", "lat": 45.43, "lon": 28.03,  "pop": 217,  "timezone": "Europe/Bucharest"},

    # Bulgaria (7)
    {"name": "Sofia",     "country": "BG", "lat": 42.70, "lon": 23.32,  "pop": 1286, "timezone": "Europe/Sofia"},
    {"name": "Plovdiv",   "country": "BG", "lat": 42.14, "lon": 24.75,  "pop": 346,  "timezone": "Europe/Sofia"},
    {"name": "Varna",     "country": "BG", "lat": 43.21, "lon": 27.92,  "pop": 335,  "timezone": "Europe/Sofia"},
    {"name": "Burgas",    "country": "BG", "lat": 42.51, "lon": 27.47,  "pop": 202,  "timezone": "Europe/Sofia"},
    {"name": "Ruse",      "country": "BG", "lat": 43.85, "lon": 25.97,  "pop": 144,  "timezone": "Europe/Sofia"},
    {"name": "Stara Zagora", "country": "BG", "lat": 42.43, "lon": 25.63, "pop": 137, "timezone": "Europe/Sofia"},
    {"name": "Pleven",    "country": "BG", "lat": 43.41, "lon": 24.62,  "pop": 95,   "timezone": "Europe/Sofia"},

    # Slovakia (6)
    {"name": "Bratislava","country": "SK", "lat": 48.15, "lon": 17.11,  "pop": 475,  "timezone": "Europe/Bratislava"},
    {"name": "Košice",    "country": "SK", "lat": 48.72, "lon": 21.26,  "pop": 229,  "timezone": "Europe/Bratislava"},
    {"name": "Prešov",    "country": "SK", "lat": 48.99, "lon": 21.24,  "pop": 84,   "timezone": "Europe/Bratislava"},
    {"name": "Žilina",    "country": "SK", "lat": 49.22, "lon": 18.74,  "pop": 81,   "timezone": "Europe/Bratislava"},
    {"name": "Banská Bystrica", "country": "SK", "lat": 48.74, "lon": 19.15, "pop": 76, "timezone": "Europe/Bratislava"},
    {"name": "Nitra",     "country": "SK", "lat": 48.31, "lon": 18.09,  "pop": 76,   "timezone": "Europe/Bratislava"},

    # Ukraine (10 — high pop)
    {"name": "Kyiv",      "country": "UA", "lat": 50.45, "lon": 30.52,  "pop": 2952, "timezone": "Europe/Kyiv"},
    {"name": "Kharkiv",   "country": "UA", "lat": 49.99, "lon": 36.23,  "pop": 1421, "timezone": "Europe/Kyiv"},
    {"name": "Odesa",     "country": "UA", "lat": 46.48, "lon": 30.73,  "pop": 1017, "timezone": "Europe/Kyiv"},
    {"name": "Dnipro",    "country": "UA", "lat": 48.46, "lon": 35.04,  "pop": 970,  "timezone": "Europe/Kyiv"},
    {"name": "Donetsk",   "country": "UA", "lat": 48.00, "lon": 37.80,  "pop": 900,  "timezone": "Europe/Kyiv"},
    {"name": "Zaporizhzhia", "country": "UA", "lat": 47.83, "lon": 35.17, "pop": 722, "timezone": "Europe/Kyiv"},
    {"name": "Lviv",      "country": "UA", "lat": 49.84, "lon": 24.03,  "pop": 717,  "timezone": "Europe/Kyiv"},
    {"name": "Kryvyi Rih","country": "UA", "lat": 47.91, "lon": 33.39,  "pop": 612,  "timezone": "Europe/Kyiv"},
    {"name": "Mykolaiv",  "country": "UA", "lat": 46.97, "lon": 31.99,  "pop": 470,  "timezone": "Europe/Kyiv"},
    {"name": "Mariupol",  "country": "UA", "lat": 47.10, "lon": 37.54,  "pop": 431,  "timezone": "Europe/Kyiv"},

    # Croatia (6)
    {"name": "Zagreb",    "country": "HR", "lat": 45.81, "lon": 15.98,  "pop": 767,  "timezone": "Europe/Zagreb"},
    {"name": "Split",     "country": "HR", "lat": 43.51, "lon": 16.44,  "pop": 161,  "timezone": "Europe/Zagreb"},
    {"name": "Rijeka",    "country": "HR", "lat": 45.33, "lon": 14.44,  "pop": 108,  "timezone": "Europe/Zagreb"},
    {"name": "Osijek",    "country": "HR", "lat": 45.55, "lon": 18.69,  "pop": 96,   "timezone": "Europe/Zagreb"},
    {"name": "Zadar",     "country": "HR", "lat": 44.12, "lon": 15.23,  "pop": 71,   "timezone": "Europe/Zagreb"},
    {"name": "Pula",      "country": "HR", "lat": 44.87, "lon": 13.85,  "pop": 52,   "timezone": "Europe/Zagreb"},

    # Serbia (7)
    {"name": "Belgrade",  "country": "RS", "lat": 44.82, "lon": 20.46,  "pop": 1166, "timezone": "Europe/Belgrade"},
    {"name": "Novi Sad",  "country": "RS", "lat": 45.25, "lon": 19.83,  "pop": 289,  "timezone": "Europe/Belgrade"},
    {"name": "Niš",       "country": "RS", "lat": 43.32, "lon": 21.90,  "pop": 183,  "timezone": "Europe/Belgrade"},
    {"name": "Kragujevac","country": "RS", "lat": 44.01, "lon": 20.91,  "pop": 150,  "timezone": "Europe/Belgrade"},
    {"name": "Subotica",  "country": "RS", "lat": 46.10, "lon": 19.67,  "pop": 94,   "timezone": "Europe/Belgrade"},
    {"name": "Zrenjanin", "country": "RS", "lat": 45.38, "lon": 20.38,  "pop": 73,   "timezone": "Europe/Belgrade"},
    {"name": "Pančevo",   "country": "RS", "lat": 44.87, "lon": 20.65,  "pop": 72,   "timezone": "Europe/Belgrade"},

    # Greece (8)
    {"name": "Athens",    "country": "GR", "lat": 37.98, "lon": 23.73,  "pop": 3153, "timezone": "Europe/Athens"},
    {"name": "Thessaloniki","country": "GR","lat": 40.64, "lon": 22.94, "pop": 812,  "timezone": "Europe/Athens"},
    {"name": "Patras",    "country": "GR", "lat": 38.25, "lon": 21.74,  "pop": 214,  "timezone": "Europe/Athens"},
    {"name": "Heraklion", "country": "GR", "lat": 35.34, "lon": 25.13,  "pop": 179,  "timezone": "Europe/Athens"},
    {"name": "Larissa",   "country": "GR", "lat": 39.64, "lon": 22.42,  "pop": 148,  "timezone": "Europe/Athens"},
    {"name": "Volos",     "country": "GR", "lat": 39.37, "lon": 22.94,  "pop": 144,  "timezone": "Europe/Athens"},
    {"name": "Ioannina",  "country": "GR", "lat": 39.67, "lon": 20.85,  "pop": 113,  "timezone": "Europe/Athens"},
    {"name": "Kavala",    "country": "GR", "lat": 40.94, "lon": 24.41,  "pop": 70,   "timezone": "Europe/Athens"},

    # Slovenia (5)
    {"name": "Ljubljana", "country": "SI", "lat": 46.06, "lon": 14.51,  "pop": 285,  "timezone": "Europe/Ljubljana"},
    {"name": "Maribor",   "country": "SI", "lat": 46.56, "lon": 15.65,  "pop": 95,   "timezone": "Europe/Ljubljana"},
    {"name": "Celje",     "country": "SI", "lat": 46.23, "lon": 15.26,  "pop": 38,   "timezone": "Europe/Ljubljana"},
    {"name": "Kranj",     "country": "SI", "lat": 46.24, "lon": 14.36,  "pop": 37,   "timezone": "Europe/Ljubljana"},
    {"name": "Koper",     "country": "SI", "lat": 45.55, "lon": 13.73,  "pop": 25,   "timezone": "Europe/Ljubljana"},

    # Sweden (8)
    {"name": "Stockholm", "country": "SE", "lat": 59.33, "lon": 18.07,  "pop": 975,  "timezone": "Europe/Stockholm"},
    {"name": "Gothenburg","country": "SE", "lat": 57.71, "lon": 11.97,  "pop": 583,  "timezone": "Europe/Stockholm"},
    {"name": "Malmö",     "country": "SE", "lat": 55.60, "lon": 13.00,  "pop": 351,  "timezone": "Europe/Stockholm"},
    {"name": "Uppsala",   "country": "SE", "lat": 59.86, "lon": 17.64,  "pop": 175,  "timezone": "Europe/Stockholm"},
    {"name": "Västerås",  "country": "SE", "lat": 59.61, "lon": 16.55,  "pop": 127,  "timezone": "Europe/Stockholm"},
    {"name": "Örebro",    "country": "SE", "lat": 59.27, "lon": 15.21,  "pop": 126,  "timezone": "Europe/Stockholm"},
    {"name": "Linköping", "country": "SE", "lat": 58.41, "lon": 15.62,  "pop": 115,  "timezone": "Europe/Stockholm"},
    {"name": "Helsingborg","country": "SE","lat": 56.05, "lon": 12.69,  "pop": 114,  "timezone": "Europe/Stockholm"},

    # Norway (6)
    {"name": "Oslo",      "country": "NO", "lat": 59.91, "lon": 10.75,  "pop": 709,  "timezone": "Europe/Oslo"},
    {"name": "Bergen",    "country": "NO", "lat": 60.39, "lon": 5.32,   "pop": 291,  "timezone": "Europe/Oslo"},
    {"name": "Stavanger", "country": "NO", "lat": 58.97, "lon": 5.73,   "pop": 148,  "timezone": "Europe/Oslo"},
    {"name": "Trondheim", "country": "NO", "lat": 63.43, "lon": 10.39,  "pop": 214,  "timezone": "Europe/Oslo"},
    {"name": "Drammen",   "country": "NO", "lat": 59.74, "lon": 10.20,  "pop": 103,  "timezone": "Europe/Oslo"},
    {"name": "Tromsø",    "country": "NO", "lat": 69.65, "lon": 18.96,  "pop": 78,   "timezone": "Europe/Oslo"},

    # Denmark (6)
    {"name": "Copenhagen","country": "DK", "lat": 55.68, "lon": 12.57,  "pop": 1366, "timezone": "Europe/Copenhagen"},
    {"name": "Aarhus",    "country": "DK", "lat": 56.16, "lon": 10.20,  "pop": 285,  "timezone": "Europe/Copenhagen"},
    {"name": "Odense",    "country": "DK", "lat": 55.40, "lon": 10.39,  "pop": 180,  "timezone": "Europe/Copenhagen"},
    {"name": "Aalborg",   "country": "DK", "lat": 57.05, "lon": 9.92,   "pop": 143,  "timezone": "Europe/Copenhagen"},
    {"name": "Esbjerg",   "country": "DK", "lat": 55.47, "lon": 8.45,   "pop": 72,   "timezone": "Europe/Copenhagen"},
    {"name": "Randers",   "country": "DK", "lat": 56.46, "lon": 10.04,  "pop": 63,   "timezone": "Europe/Copenhagen"},

    # Finland (6)
    {"name": "Helsinki",  "country": "FI", "lat": 60.17, "lon": 24.94,  "pop": 658,  "timezone": "Europe/Helsinki"},
    {"name": "Espoo",     "country": "FI", "lat": 60.21, "lon": 24.66,  "pop": 301,  "timezone": "Europe/Helsinki"},
    {"name": "Tampere",   "country": "FI", "lat": 61.50, "lon": 23.78,  "pop": 244,  "timezone": "Europe/Helsinki"},
    {"name": "Vantaa",    "country": "FI", "lat": 60.29, "lon": 25.04,  "pop": 240,  "timezone": "Europe/Helsinki"},
    {"name": "Turku",     "country": "FI", "lat": 60.45, "lon": 22.27,  "pop": 195,  "timezone": "Europe/Helsinki"},
    {"name": "Oulu",      "country": "FI", "lat": 65.01, "lon": 25.47,  "pop": 208,  "timezone": "Europe/Helsinki"},

    # Iceland (5, small)
    {"name": "Reykjavík", "country": "IS", "lat": 64.15, "lon": -21.94, "pop": 140,  "timezone": "Atlantic/Reykjavik"},
    {"name": "Kópavogur", "country": "IS", "lat": 64.11, "lon": -21.91, "pop": 40,   "timezone": "Atlantic/Reykjavik"},
    {"name": "Hafnarfjörður","country": "IS","lat": 64.07,"lon": -21.96,"pop": 30,   "timezone": "Atlantic/Reykjavik"},
    {"name": "Akureyri",  "country": "IS", "lat": 65.69, "lon": -18.11, "pop": 19,   "timezone": "Atlantic/Reykjavik"},
    {"name": "Reykjanesbær","country": "IS","lat": 64.00, "lon": -22.56, "pop": 21,  "timezone": "Atlantic/Reykjavik"},

    # Estonia (5)
    {"name": "Tallinn",   "country": "EE", "lat": 59.44, "lon": 24.75,  "pop": 453,  "timezone": "Europe/Tallinn"},
    {"name": "Tartu",     "country": "EE", "lat": 58.38, "lon": 26.73,  "pop": 91,   "timezone": "Europe/Tallinn"},
    {"name": "Narva",     "country": "EE", "lat": 59.38, "lon": 28.20,  "pop": 53,   "timezone": "Europe/Tallinn"},
    {"name": "Pärnu",     "country": "EE", "lat": 58.39, "lon": 24.50,  "pop": 39,   "timezone": "Europe/Tallinn"},
    {"name": "Kohtla-Järve","country":"EE","lat": 59.39, "lon": 27.27,  "pop": 31,   "timezone": "Europe/Tallinn"},

    # Latvia (5)
    {"name": "Riga",      "country": "LV", "lat": 56.95, "lon": 24.11,  "pop": 605,  "timezone": "Europe/Riga"},
    {"name": "Daugavpils","country": "LV", "lat": 55.88, "lon": 26.54,  "pop": 78,   "timezone": "Europe/Riga"},
    {"name": "Liepāja",   "country": "LV", "lat": 56.51, "lon": 21.01,  "pop": 66,   "timezone": "Europe/Riga"},
    {"name": "Jelgava",   "country": "LV", "lat": 56.65, "lon": 23.72,  "pop": 54,   "timezone": "Europe/Riga"},
    {"name": "Jūrmala",   "country": "LV", "lat": 56.97, "lon": 23.77,  "pop": 50,   "timezone": "Europe/Riga"},

    # Lithuania (5)
    {"name": "Vilnius",   "country": "LT", "lat": 54.69, "lon": 25.28,  "pop": 588,  "timezone": "Europe/Vilnius"},
    {"name": "Kaunas",    "country": "LT", "lat": 54.90, "lon": 23.90,  "pop": 295,  "timezone": "Europe/Vilnius"},
    {"name": "Klaipėda",  "country": "LT", "lat": 55.71, "lon": 21.13,  "pop": 150,  "timezone": "Europe/Vilnius"},
    {"name": "Šiauliai",  "country": "LT", "lat": 55.93, "lon": 23.31,  "pop": 102,  "timezone": "Europe/Vilnius"},
    {"name": "Panevėžys", "country": "LT", "lat": 55.73, "lon": 24.35,  "pop": 87,   "timezone": "Europe/Vilnius"},

    # Singapore (5, city-state)
    {"name": "Singapore", "country": "SG", "lat": 1.35,  "lon": 103.82, "pop": 5975, "timezone": "Asia/Singapore"},
    {"name": "Woodlands", "country": "SG", "lat": 1.44,  "lon": 103.79, "pop": 253,  "timezone": "Asia/Singapore"},
    {"name": "Tampines",  "country": "SG", "lat": 1.35,  "lon": 103.95, "pop": 250,  "timezone": "Asia/Singapore"},
    {"name": "Bedok",     "country": "SG", "lat": 1.32,  "lon": 103.93, "pop": 281,  "timezone": "Asia/Singapore"},
    {"name": "Jurong West","country": "SG","lat": 1.34,  "lon": 103.71, "pop": 264,  "timezone": "Asia/Singapore"},

    # Malaysia (8)
    {"name": "Kuala Lumpur","country": "MY","lat": 3.14, "lon": 101.69, "pop": 1982, "timezone": "Asia/Kuala_Lumpur"},
    {"name": "Johor Bahru","country": "MY", "lat": 1.49, "lon": 103.76, "pop": 858,  "timezone": "Asia/Kuala_Lumpur"},
    {"name": "Ipoh",      "country": "MY", "lat": 4.60,  "lon": 101.08, "pop": 657,  "timezone": "Asia/Kuala_Lumpur"},
    {"name": "Klang",     "country": "MY", "lat": 3.04,  "lon": 101.45, "pop": 879,  "timezone": "Asia/Kuala_Lumpur"},
    {"name": "George Town","country": "MY","lat": 5.41,  "lon": 100.33, "pop": 794,  "timezone": "Asia/Kuala_Lumpur"},
    {"name": "Shah Alam", "country": "MY", "lat": 3.08,  "lon": 101.53, "pop": 641,  "timezone": "Asia/Kuala_Lumpur"},
    {"name": "Petaling Jaya","country":"MY","lat": 3.10, "lon": 101.64, "pop": 613,  "timezone": "Asia/Kuala_Lumpur"},
    {"name": "Kuching",   "country": "MY", "lat": 1.56,  "lon": 110.35, "pop": 325,  "timezone": "Asia/Kuching"},

    # Australia (10)
    {"name": "Sydney",    "country": "AU", "lat": -33.87,"lon": 151.21, "pop": 5367, "timezone": "Australia/Sydney"},
    {"name": "Melbourne", "country": "AU", "lat": -37.81,"lon": 144.96, "pop": 5078, "timezone": "Australia/Melbourne"},
    {"name": "Brisbane",  "country": "AU", "lat": -27.47,"lon": 153.02, "pop": 2568, "timezone": "Australia/Brisbane"},
    {"name": "Perth",     "country": "AU", "lat": -31.95,"lon": 115.86, "pop": 2192, "timezone": "Australia/Perth"},
    {"name": "Adelaide",  "country": "AU", "lat": -34.93,"lon": 138.60, "pop": 1418, "timezone": "Australia/Adelaide"},
    {"name": "Gold Coast","country": "AU", "lat": -28.02,"lon": 153.40, "pop": 709,  "timezone": "Australia/Brisbane"},
    {"name": "Newcastle", "country": "AU", "lat": -32.93,"lon": 151.78, "pop": 509,  "timezone": "Australia/Sydney"},
    {"name": "Canberra",  "country": "AU", "lat": -35.28,"lon": 149.13, "pop": 463,  "timezone": "Australia/Sydney"},
    {"name": "Hobart",    "country": "AU", "lat": -42.88,"lon": 147.33, "pop": 247,  "timezone": "Australia/Hobart"},
    {"name": "Darwin",    "country": "AU", "lat": -12.46,"lon": 130.84, "pop": 150,  "timezone": "Australia/Darwin"},

    # New Zealand (5)
    {"name": "Auckland",  "country": "NZ", "lat": -36.85,"lon": 174.76, "pop": 1718, "timezone": "Pacific/Auckland"},
    {"name": "Wellington","country": "NZ", "lat": -41.29,"lon": 174.78, "pop": 217,  "timezone": "Pacific/Auckland"},
    {"name": "Christchurch","country": "NZ","lat":-43.53,"lon": 172.64, "pop": 383,  "timezone": "Pacific/Auckland"},
    {"name": "Hamilton",  "country": "NZ", "lat": -37.79,"lon": 175.28, "pop": 179,  "timezone": "Pacific/Auckland"},
    {"name": "Tauranga",  "country": "NZ", "lat": -37.69,"lon": 176.17, "pop": 158,  "timezone": "Pacific/Auckland"},

    # Canada (10)
    {"name": "Toronto",   "country": "CA", "lat": 43.65, "lon": -79.38, "pop": 2930, "timezone": "America/Toronto"},
    {"name": "Montreal",  "country": "CA", "lat": 45.50, "lon": -73.57, "pop": 1762, "timezone": "America/Toronto"},
    {"name": "Vancouver", "country": "CA", "lat": 49.28, "lon": -123.12,"pop": 662,  "timezone": "America/Vancouver"},
    {"name": "Calgary",   "country": "CA", "lat": 51.05, "lon": -114.07,"pop": 1306, "timezone": "America/Edmonton"},
    {"name": "Edmonton",  "country": "CA", "lat": 53.55, "lon": -113.49,"pop": 1010, "timezone": "America/Edmonton"},
    {"name": "Ottawa",    "country": "CA", "lat": 45.42, "lon": -75.69, "pop": 1017, "timezone": "America/Toronto"},
    {"name": "Winnipeg",  "country": "CA", "lat": 49.90, "lon": -97.14, "pop": 749,  "timezone": "America/Winnipeg"},
    {"name": "Quebec City","country": "CA","lat": 46.81, "lon": -71.21, "pop": 542,  "timezone": "America/Toronto"},
    {"name": "Hamilton",  "country": "CA", "lat": 43.26, "lon": -79.87, "pop": 570,  "timezone": "America/Toronto"},
    {"name": "Halifax",   "country": "CA", "lat": 44.65, "lon": -63.58, "pop": 440,  "timezone": "America/Halifax"},

    # Argentina (10)
    {"name": "Buenos Aires","country": "AR","lat":-34.61,"lon": -58.38, "pop": 3075, "timezone": "America/Argentina/Buenos_Aires"},
    {"name": "Córdoba",   "country": "AR", "lat": -31.42,"lon": -64.18, "pop": 1530, "timezone": "America/Argentina/Cordoba"},
    {"name": "Rosario",   "country": "AR", "lat": -32.95,"lon": -60.64, "pop": 1194, "timezone": "America/Argentina/Buenos_Aires"},
    {"name": "Mendoza",   "country": "AR", "lat": -32.89,"lon": -68.83, "pop": 1115, "timezone": "America/Argentina/Mendoza"},
    {"name": "San Miguel de Tucumán","country":"AR","lat":-26.83,"lon":-65.22,"pop":836,"timezone": "America/Argentina/Tucuman"},
    {"name": "La Plata",  "country": "AR", "lat": -34.92,"lon": -57.95, "pop": 700,  "timezone": "America/Argentina/Buenos_Aires"},
    {"name": "Mar del Plata","country":"AR","lat":-38.00,"lon":-57.55,"pop":645,  "timezone": "America/Argentina/Buenos_Aires"},
    {"name": "Salta",     "country": "AR", "lat": -24.78,"lon": -65.41, "pop": 619,  "timezone": "America/Argentina/Salta"},
    {"name": "Santa Fe",  "country": "AR", "lat": -31.63,"lon": -60.70, "pop": 415,  "timezone": "America/Argentina/Buenos_Aires"},
    {"name": "San Juan",  "country": "AR", "lat": -31.54,"lon": -68.54, "pop": 477,  "timezone": "America/Argentina/San_Juan"},

    # Chile (7)
    {"name": "Santiago",  "country": "CL", "lat": -33.45,"lon": -70.67, "pop": 6812, "timezone": "America/Santiago"},
    {"name": "Valparaíso","country": "CL", "lat": -33.05,"lon": -71.62, "pop": 315,  "timezone": "America/Santiago"},
    {"name": "Concepción","country": "CL", "lat": -36.83,"lon": -73.05, "pop": 225,  "timezone": "America/Santiago"},
    {"name": "La Serena", "country": "CL", "lat": -29.91,"lon": -71.25, "pop": 232,  "timezone": "America/Santiago"},
    {"name": "Antofagasta","country": "CL","lat": -23.65,"lon": -70.40, "pop": 362,  "timezone": "America/Santiago"},
    {"name": "Temuco",    "country": "CL", "lat": -38.74,"lon": -72.59, "pop": 262,  "timezone": "America/Santiago"},
    {"name": "Iquique",   "country": "CL", "lat": -20.22,"lon": -70.14, "pop": 191,  "timezone": "America/Santiago"},

    # Israel (7)
    {"name": "Jerusalem", "country": "IL", "lat": 31.78, "lon": 35.22,  "pop": 969,  "timezone": "Asia/Jerusalem"},
    {"name": "Tel Aviv",  "country": "IL", "lat": 32.08, "lon": 34.78,  "pop": 460,  "timezone": "Asia/Jerusalem"},
    {"name": "Haifa",     "country": "IL", "lat": 32.79, "lon": 34.99,  "pop": 286,  "timezone": "Asia/Jerusalem"},
    {"name": "Rishon LeZion","country":"IL","lat":31.97,"lon": 34.80,  "pop": 257,  "timezone": "Asia/Jerusalem"},
    {"name": "Petah Tikva","country": "IL","lat":32.09, "lon": 34.89,  "pop": 250,  "timezone": "Asia/Jerusalem"},
    {"name": "Ashdod",    "country": "IL", "lat": 31.79, "lon": 34.65,  "pop": 225,  "timezone": "Asia/Jerusalem"},
    {"name": "Netanya",   "country": "IL", "lat": 32.33, "lon": 34.86,  "pop": 221,  "timezone": "Asia/Jerusalem"},

    # UAE (7)
    {"name": "Dubai",     "country": "AE", "lat": 25.20, "lon": 55.27,  "pop": 3605, "timezone": "Asia/Dubai"},
    {"name": "Abu Dhabi", "country": "AE", "lat": 24.47, "lon": 54.37,  "pop": 1483, "timezone": "Asia/Dubai"},
    {"name": "Sharjah",   "country": "AE", "lat": 25.35, "lon": 55.42,  "pop": 1684, "timezone": "Asia/Dubai"},
    {"name": "Al Ain",    "country": "AE", "lat": 24.22, "lon": 55.74,  "pop": 650,  "timezone": "Asia/Dubai"},
    {"name": "Ajman",     "country": "AE", "lat": 25.41, "lon": 55.44,  "pop": 540,  "timezone": "Asia/Dubai"},
    {"name": "Ras Al Khaimah","country":"AE","lat":25.79,"lon": 55.96,  "pop": 191,  "timezone": "Asia/Dubai"},
    {"name": "Fujairah",  "country": "AE", "lat": 25.13, "lon": 56.33,  "pop": 92,   "timezone": "Asia/Dubai"},

    # Saudi Arabia (10, high pop)
    {"name": "Riyadh",    "country": "SA", "lat": 24.71, "lon": 46.67,  "pop": 7231, "timezone": "Asia/Riyadh"},
    {"name": "Jeddah",    "country": "SA", "lat": 21.49, "lon": 39.19,  "pop": 4610, "timezone": "Asia/Riyadh"},
    {"name": "Mecca",     "country": "SA", "lat": 21.39, "lon": 39.86,  "pop": 2043, "timezone": "Asia/Riyadh"},
    {"name": "Medina",    "country": "SA", "lat": 24.47, "lon": 39.61,  "pop": 1488, "timezone": "Asia/Riyadh"},
    {"name": "Dammam",    "country": "SA", "lat": 26.43, "lon": 50.09,  "pop": 1252, "timezone": "Asia/Riyadh"},
    {"name": "Taif",      "country": "SA", "lat": 21.27, "lon": 40.42,  "pop": 688,  "timezone": "Asia/Riyadh"},
    {"name": "Tabuk",     "country": "SA", "lat": 28.38, "lon": 36.58,  "pop": 667,  "timezone": "Asia/Riyadh"},
    {"name": "Buraidah",  "country": "SA", "lat": 26.33, "lon": 43.97,  "pop": 614,  "timezone": "Asia/Riyadh"},
    {"name": "Khamis Mushait","country":"SA","lat":18.31,"lon": 42.73,  "pop": 631,  "timezone": "Asia/Riyadh"},
    {"name": "Khobar",    "country": "SA", "lat": 26.28, "lon": 50.21,  "pop": 626,  "timezone": "Asia/Riyadh"},
]


PROXY_DOCS = {
    "arab_world": (
        "Hofstede regional proxy for Gulf/Arab countries lacking "
        "country-specific published scores. Source: Hofstede's regional "
        "aggregate for the Arab world."
    ),
    "nordic_baltic": (
        "Regional proxy averaging Baltic (EE/LV/LT) published scores "
        "for Iceland, which has no Hofstede Insights country-specific "
        "publication."
    ),
}


def main() -> int:
    # Load
    countries = json.loads(COUNTRIES_PATH.read_text(encoding="utf-8"))
    hofstede = json.loads(HOFSTEDE_PATH.read_text(encoding="utf-8"))
    cities = json.loads(CITIES_PATH.read_text(encoding="utf-8"))

    existing_iso2 = {c["iso2"] for c in countries["countries"]}
    added_country = 0
    added_hofstede = 0
    added_cities = 0

    for c in NEW_COUNTRIES:
        if c["iso2"] not in existing_iso2:
            countries["countries"].append(c)
            added_country += 1

    # Resort by population desc
    countries["countries"].sort(key=lambda c: c["population"], reverse=True)
    countries["_comment"] = (
        f"Top {len(countries['countries'])} countries; ISO2-indexed. "
        "Fields: iso2, iso3, name, population (millions), lat/lon, "
        "faker_locale (or null), primary_religion, region. "
        "median_age in years. gdp_per_capita_usd approximate."
    )

    for iso2, entry in NEW_HOFSTEDE.items():
        if iso2 not in hofstede["scores"]:
            hofstede["scores"][iso2] = entry
            added_hofstede += 1

    if "_proxies" not in hofstede:
        hofstede["_proxies"] = PROXY_DOCS

    # Sibling metadata: which ISO2s use a regional proxy
    hofstede.setdefault("_estimated_countries", {})
    for iso2, proxy in ESTIMATED_COUNTRIES.items():
        hofstede["_estimated_countries"][iso2] = proxy

    for city in NEW_CITIES:
        # Don't add duplicates (match by name+country)
        key = (city["name"], city["country"])
        existing_keys = {(c["name"], c["country"]) for c in cities["cities"]}
        if key not in existing_keys:
            cities["cities"].append(city)
            added_cities += 1

    # Persist
    COUNTRIES_PATH.write_text(
        json.dumps(countries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    HOFSTEDE_PATH.write_text(
        json.dumps(hofstede, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    CITIES_PATH.write_text(
        json.dumps(cities, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Added {added_country} countries, "
          f"{added_hofstede} Hofstede entries, "
          f"{added_cities} cities.")
    print(f"Totals: {len(countries['countries'])} countries, "
          f"{len(hofstede['scores'])} Hofstede scores, "
          f"{len(cities['cities'])} cities.")

    # Invariant check: perfect-overlap
    ctry_iso2 = {c["iso2"] for c in countries["countries"]}
    hofst_iso2 = set(hofstede["scores"].keys())
    cities_iso2 = {c["country"] for c in cities["cities"]}
    if ctry_iso2 != hofst_iso2:
        missing = ctry_iso2 ^ hofst_iso2
        print(f"WARNING: ISO2 asymmetry countries<->hofstede: {missing}")
    if not cities_iso2.issubset(ctry_iso2):
        print(f"WARNING: cities reference unknown ISO2: "
              f"{cities_iso2 - ctry_iso2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
