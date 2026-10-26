# api/services/sun.py
"""
Éblouissement par le soleil : position du soleil (algorithme NOAA simplifié, précision < 1°)
comparée à la direction de la route. Soleil bas (0-25° au-dessus de l'horizon) et dans l'axe
de conduite (± 30°) = risque d'éblouissement, typique au lever et au coucher.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

GLARE_MAX_ELEVATION = 25.0
GLARE_MAX_AZIMUTH_DIFF = 30.0


def solar_position(lat: float, lng: float, when_utc: datetime) -> tuple[float, float]:
    """(élévation, azimut) du soleil en degrés ; azimut compté depuis le nord, sens horaire."""
    t = when_utc.astimezone(timezone.utc)
    doy = t.timetuple().tm_yday
    hour = t.hour + t.minute / 60 + t.second / 3600
    g = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    tst = hour * 60 + eqtime + 4 * lng
    ha = math.radians(tst / 4 - 180)
    phi = math.radians(lat)
    cos_zen = math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(ha)
    zen = math.acos(max(-1.0, min(1.0, cos_zen)))
    elevation = 90 - math.degrees(zen)
    az = math.degrees(math.atan2(math.sin(ha), math.cos(ha) * math.sin(phi) - math.tan(decl) * math.cos(phi)))
    return elevation, (az + 180) % 360


def bearing(a: list[float], b: list[float]) -> float:
    """Cap (degrés depuis le nord) du point a [lat, lng] vers b."""
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    x = math.sin(dl) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def heading_at(geometry: list[list[float]], index: int, span: int = 5) -> float:
    i0 = max(0, index - span)
    i1 = min(len(geometry) - 1, index + span)
    if i0 == i1:
        return 0.0
    return bearing(geometry[i0], geometry[i1])


def glare(lat: float, lng: float, heading: float, local_time: str, utc_offset_s: int) -> dict | None:
    """Éblouissement au passage (heure locale ISO de la prévision) ; None si le soleil ne gêne pas."""
    local = datetime.fromisoformat(local_time)
    when = datetime.fromtimestamp(local.replace(tzinfo=timezone.utc).timestamp() - utc_offset_s, tz=timezone.utc)
    elevation, azimuth = solar_position(lat, lng, when)
    diff = abs((azimuth - heading + 180) % 360 - 180)
    if 0 < elevation <= GLARE_MAX_ELEVATION and diff <= GLARE_MAX_AZIMUTH_DIFF:
        return {"sun_elevation": round(elevation, 1), "sun_azimuth": round(azimuth), "angle_to_road": round(diff)}
    return None
