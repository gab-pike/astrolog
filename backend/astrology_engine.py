"""
astrolog — core calculation engine
Swiss Ephemeris (pyswisseph) based astrology calculations.

Works out of the box with the built-in Moshier ephemeris (no data files
needed, ~0.1 arcsec planetary accuracy — far beyond astrological needs).
If you download Swiss Ephemeris .se1 files into the ephe/ directory,
they are picked up automatically for maximum precision.
"""

import math
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

# --- Ephemeris setup -------------------------------------------------------
EPHE_PATH = os.environ.get("EPHE_PATH", os.path.join(os.path.dirname(__file__), "..", "ephe"))
_HAS_EPHE_FILES = os.path.isdir(EPHE_PATH) and any(
    f.endswith(".se1") for f in os.listdir(EPHE_PATH)
) if os.path.isdir(EPHE_PATH) else False

if _HAS_EPHE_FILES:
    swe.set_ephe_path(EPHE_PATH)
    CALC_FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED
else:
    CALC_FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED  # built-in, no files needed

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO, "North Node": swe.MEAN_NODE, "Lilith": swe.MEAN_APOG, "Chiron": swe.CHIRON,
}

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

ASPECTS = [
    ("Conjunction", 0, 8.0),
    ("Sextile", 60, 4.0),
    ("Square", 90, 6.0),
    ("Trine", 120, 6.0),
    ("Opposition", 180, 8.0),
]

MOON_PHASES = [
    (22.5, "New Moon"), (67.5, "Waxing Crescent"), (112.5, "First Quarter"),
    (157.5, "Waxing Gibbous"), (202.5, "Full Moon"), (247.5, "Waning Gibbous"),
    (292.5, "Last Quarter"), (337.5, "Waning Crescent"), (360.0, "New Moon"),
]


def _julian_day(dt_utc: datetime) -> float:
    """UTC datetime -> Julian day (UT)."""
    frac_hour = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, frac_hour)


def _sign_and_degree(longitude: float):
    longitude = longitude % 360.0
    sign = SIGNS[int(longitude // 30)]
    degree = longitude % 30.0
    d = int(degree)
    m = int(round((degree - d) * 60))
    if m == 60:
        d, m = d + 1, 0
    return sign, degree, f"{d}°{m:02d}′"


def _positions(jd: float) -> dict:
    """Longitude, sign, degree, retrograde flag for every body."""
    out = {}
    for name, body in PLANETS.items():
        try:
            xx, _ = swe.calc_ut(jd, body, CALC_FLAGS)
        except swe.Error:
            continue  # Chiron needs seas files with SWIEPH; skip gracefully
        lon_deg, speed = xx[0], xx[3]
        sign, degree, pretty = _sign_and_degree(lon_deg)
        out[name] = {
            "longitude": round(lon_deg, 4),
            "sign": sign,
            "degree": round(degree, 2),
            "pretty": pretty,
            "retrograde": speed < 0 and name not in ("Sun", "Moon"),
        }
    return out


def _houses(jd: float, geo_lat: float, geo_lon: float) -> dict:
    """Placidus house cusps + angles. Note: geographic lon/lat are named
    distinctly so nothing shadows them (the classic bug)."""
    cusps, ascmc = swe.houses(jd, geo_lat, geo_lon, b"P")
    house_list = []
    for i, cusp in enumerate(cusps, start=1):
        sign, degree, pretty = _sign_and_degree(cusp)
        house_list.append({"house": i, "longitude": round(cusp, 4),
                           "sign": sign, "pretty": pretty})
    asc_sign, _, asc_pretty = _sign_and_degree(ascmc[0])
    mc_sign, _, mc_pretty = _sign_and_degree(ascmc[1])
    return {
        "cusps": house_list,
        "ascendant": {"longitude": round(ascmc[0], 4), "sign": asc_sign, "pretty": asc_pretty},
        "midheaven": {"longitude": round(ascmc[1], 4), "sign": mc_sign, "pretty": mc_pretty},
    }


def _angular_separation(a: float, b: float) -> float:
    diff = abs(a - b) % 360.0
    return 360.0 - diff if diff > 180.0 else diff


def _aspects_between(set_a: dict, set_b: dict = None) -> list:
    """Aspects within one set of positions, or between two sets
    (e.g. transiting planets vs natal planets)."""
    results = []
    if set_b is None:
        items = list(set_a.items())
        pairs = [(items[i], items[j]) for i in range(len(items))
                 for j in range(i + 1, len(items))]
        cross = False
    else:
        pairs = [((na, pa), (nb, pb)) for na, pa in set_a.items()
                 for nb, pb in set_b.items()]
        cross = True
    for (name_a, pos_a), (name_b, pos_b) in pairs:
        sep = _angular_separation(pos_a["longitude"], pos_b["longitude"])
        for aspect_name, angle, max_orb in ASPECTS:
            orb = abs(sep - angle)
            if orb <= max_orb:
                results.append({
                    "a": name_a, "b": (name_b + " (natal)") if cross else name_b,
                    "aspect": aspect_name, "orb": round(orb, 2),
                })
                break
    results.sort(key=lambda x: x["orb"])
    return results


def _moon_phase(positions: dict) -> dict:
    elong = (positions["Moon"]["longitude"] - positions["Sun"]["longitude"]) % 360.0
    illum = (1 - math.cos(math.radians(elong))) / 2.0
    name = next(label for limit, label in MOON_PHASES if elong < limit)
    return {"phase": name, "elongation": round(elong, 2),
            "illumination_pct": round(illum * 100, 1),
            "waxing": elong < 180.0}


def current_chart(geo_lat: float, geo_lon: float) -> dict:
    """Full snapshot of the sky right now."""
    now = datetime.now(timezone.utc)
    jd = _julian_day(now)
    positions = _positions(jd)
    return {
        "timestamp_utc": now.isoformat(),
        "positions": positions,
        "houses": _houses(jd, geo_lat, geo_lon),
        "aspects": _aspects_between(positions),
        "moon": _moon_phase(positions),
    }


def natal_chart(date_str: str, time_str: str, tz_name: str,
                geo_lat: float, geo_lon: float) -> dict:
    """Natal chart from local birth date/time + IANA timezone."""
    local = datetime.fromisoformat(f"{date_str}T{time_str}").replace(tzinfo=ZoneInfo(tz_name))
    dt_utc = local.astimezone(timezone.utc)
    jd = _julian_day(dt_utc)
    positions = _positions(jd)
    return {
        "birth_local": local.isoformat(),
        "birth_utc": dt_utc.isoformat(),
        "positions": positions,
        "houses": _houses(jd, geo_lat, geo_lon),
        "aspects": _aspects_between(positions),
        "moon": _moon_phase(positions),
    }


def transits_to_natal(natal: dict, geo_lat: float, geo_lon: float) -> dict:
    """Current sky aspecting a natal chart."""
    sky = current_chart(geo_lat, geo_lon)
    sky["transit_aspects"] = _aspects_between(sky["positions"], natal["positions"])
    return sky


if __name__ == "__main__":
    import json
    print(json.dumps(current_chart(43.55, -96.73), indent=2))
