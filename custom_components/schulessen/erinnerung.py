"""Bestell-Erinnerung: prüft täglich zur eingestellten Uhrzeit, ob im Zeitraum Schultage ohne Bestellung sind."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ERINNERUNG,
    CONF_ERINNERUNG_TAGE,
    CONF_ERINNERUNG_ZEIT,
    CONF_ERINNERUNG_ZIELE,
    CONF_FERIENKALENDER,
    CONF_PORTAL,
    STANDARD_TAGE,
    STANDARD_ZEIT,
)

_LOGGER = logging.getLogger(__name__)
WT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def option(entry: ConfigEntry, key: str, default=None):
    return entry.options.get(key, entry.data.get(key, default))


def zeitraum(entry: ConfigEntry) -> int:
    try:
        return max(1, int(option(entry, CONF_ERINNERUNG_TAGE, STANDARD_TAGE)))
    except (TypeError, ValueError):
        return STANDARD_TAGE


async def _ferientage(hass: HomeAssistant, kalender: str | None, bis: date) -> set[str]:
    if not kalender:
        return set()
    heute = dt_util.now().date()
    try:
        res = await hass.services.async_call(
            "calendar", "get_events",
            {"entity_id": kalender,
             "start_date_time": dt_util.start_of_local_day(heute).isoformat(),
             "end_date_time": dt_util.start_of_local_day(bis + timedelta(days=1)).isoformat()},
            blocking=True, return_response=True)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Ferienkalender %s nicht lesbar: %s", kalender, err)
        return set()
    tage: set[str] = set()
    for ev in (res or {}).get(kalender, {}).get("events", []):
        s, e = str(ev.get("start", "")), str(ev.get("end", ""))
        try:
            a = date.fromisoformat(s[:10])
            b = date.fromisoformat(e[:10]) if e else a + timedelta(days=1)
        except ValueError:
            continue
        if len(e) <= 10 and b > a:  # Ganztagstermin: Ende exklusiv
            b -= timedelta(days=1)
        d = a
        while d <= b:
            tage.add(d.isoformat())
            d += timedelta(days=1)
    return tage


async def offene_tage(hass: HomeAssistant, entry: ConfigEntry) -> list[dict]:
    """Schultage im Zeitraum ohne Bestellung, deren Bestellschluss noch nicht vorbei ist."""
    coord = entry.runtime_data
    heute = dt_util.now().date()
    bis = heute + timedelta(days=zeitraum(entry))
    ferien = await _ferientage(hass, option(entry, CONF_FERIENKALENDER), bis)
    jetzt = dt_util.now()
    offen = []
    for d, t in sorted(((coord.data or {}).get("tage") or {}).items()):
        if not (heute.isoformat() < d <= bis.isoformat()):
            continue
        if not t.get("menues") or t.get("feiertag") or t.get("zustellpause") or t.get("bestellt"):
            continue
        if d in ferien:
            continue
        schluss = dt_util.parse_datetime(str(t.get("bestellschluss") or "")) if t.get("bestellschluss") else None
        if schluss and dt_util.as_local(schluss) < jetzt:
            continue
        offen.append({"datum": d, "bestellschluss": t.get("bestellschluss")})
    return offen


def _kurz(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{WT[x.weekday()]} {x.day}.{x.month}."


async def senden(hass: HomeAssistant, entry: ConfigEntry, *, auch_wenn_leer: bool = False) -> bool:
    ziele = option(entry, CONF_ERINNERUNG_ZIELE) or []
    if isinstance(ziele, str):
        ziele = [ziele]
    if not ziele:
        _LOGGER.warning("Erinnerung für %s: keine Empfänger eingestellt", entry.title)
        return False
    offen = await offene_tage(hass, entry)
    if not offen and not auch_wenn_leer:
        return False
    portal = option(entry, CONF_PORTAL)
    n = zeitraum(entry)
    spanne = "morgen" if n == 1 else f"in den nächsten {n} Tagen"
    if offen:
        tage = ", ".join(_kurz(o["datum"]) for o in offen)
        titel = f"Zu tun: Essen bestellen – {entry.title}"
        text = f"{spanne[0].upper() + spanne[1:]} noch nicht bestellt: {tage}."
        schluss = next((o["bestellschluss"] for o in offen if o["bestellschluss"]), None)
        if schluss:
            s = dt_util.parse_datetime(str(schluss))
            if s:
                s = dt_util.as_local(s)
                text += f" Nächster Bestellschluss: {_kurz(s.date().isoformat())} {s:%H:%M} Uhr."
    else:
        titel = f"Info: Schulessen {entry.title}"
        text = f"Für {spanne} ist alles bestellt."
    daten: dict = {}
    if portal:
        daten = {"url": portal, "clickAction": portal,
                 "actions": [{"action": "URI", "title": "Bestellen", "uri": portal}]}
    for ziel in ziele:
        dienst = ziel.split(".", 1)[-1]
        try:
            await hass.services.async_call("notify", dienst, {"title": titel, "message": text, "data": daten},
                                           blocking=True)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Erinnerung an %s fehlgeschlagen: %s", ziel, err)
    return True


@callback
def einrichten(hass: HomeAssistant, entry: ConfigEntry):
    """Täglichen Auslöser registrieren; gibt die Abmeldefunktion zurück."""
    if not option(entry, CONF_ERINNERUNG, False):
        return None
    try:
        z = time.fromisoformat(str(option(entry, CONF_ERINNERUNG_ZEIT, STANDARD_ZEIT)))
    except ValueError:
        z = time.fromisoformat(STANDARD_ZEIT)

    async def _ausloesen(_now: datetime) -> None:
        await senden(hass, entry)

    return async_track_time_change(hass, _ausloesen, hour=z.hour, minute=z.minute, second=0)
