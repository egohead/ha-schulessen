"""Bestell-Erinnerung: täglich zur eingestellten Uhrzeit und optional kurz vor Bestellschluss."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_APP_LINK,
    CONF_ERINNERUNG,
    CONF_ERINNERUNG_TAGE,
    CONF_ERINNERUNG_ZEIT,
    CONF_ERINNERUNG_ZIELE,
    CONF_FERIENKALENDER,
    CONF_PORTAL,
    CONF_VORLAUF,
    DOMAIN,
    STANDARD_TAGE,
    STANDARD_ZEIT,
)

_LOGGER = logging.getLogger(__name__)
WT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def option(entry: ConfigEntry, key: str, default=None):
    return entry.options.get(key, entry.data.get(key, default))


def vorlauf(entry: ConfigEntry) -> int:
    try:
        return max(0, int(option(entry, CONF_VORLAUF, 0) or 0))
    except (TypeError, ValueError):
        return 0


def schluss_zeit(tag: dict) -> datetime | None:
    """Bestellschluss eines Tages als lokale Zeit."""
    roh = tag.get("bestellschluss")
    if not roh:
        return None
    s = dt_util.parse_datetime(str(roh))
    if s is None:
        try:
            s = datetime.fromisoformat(str(roh))
        except ValueError:
            return None
    if s.tzinfo is None:
        s = s.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_local(s)


def ist_offen(tag: dict) -> bool:
    return (bool(tag.get("menues")) and not tag.get("feiertag") and not tag.get("zustellpause")
            and not tag.get("bestellt") and not tag.get("ausgenommen"))


def offene_tage_sync(tage: dict, bis: date | None = None) -> list[tuple[str, dict]]:
    """Kommende Schultage ohne Bestellung, deren Bestellschluss nicht vorbei ist (ohne Ferienkalender)."""
    heute = dt_util.now().date().isoformat()
    jetzt = dt_util.now()
    out = []
    for d, t in sorted((tage or {}).items()):
        if d < heute:
            continue
        if bis and d > bis.isoformat():
            continue
        if not ist_offen(t):
            continue
        s = schluss_zeit(t)
        if s and s < jetzt:
            continue
        out.append((d, t))
    return out


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
    return [{"datum": d, "bestellschluss": t.get("bestellschluss")}
            for d, t in offene_tage_sync((coord.data or {}).get("tage"), bis)
            if d > heute.isoformat() and d not in ferien]


def _kurz(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{WT[x.weekday()]} {x.day}.{x.month}."


async def senden(hass: HomeAssistant, entry: ConfigEntry, *, auch_wenn_leer: bool = False) -> bool:
    ziele = _ziele(entry)
    if not ziele:
        _LOGGER.warning("Erinnerung für %s: keine Empfänger eingestellt", entry.title)
        return False
    offen = await offene_tage(hass, entry)
    if not offen and not auch_wenn_leer:
        return False
    portal = ziel_link(entry)
    n = zeitraum(entry)
    spanne = "morgen" if n == 1 else f"in den nächsten {n} Tagen"
    if offen:
        tage = ", ".join(_kurz(o["datum"]) for o in offen)
        titel = f"Zu tun: Essen bestellen – {entry.title}"
        text = f"{spanne[0].upper() + spanne[1:]} noch nicht bestellt: {tage}."
        s = next((z for o in offen if (z := schluss_zeit(o))), None)
        if s:
            text += f" Nächster Bestellschluss: {_kurz(s.date().isoformat())} {s:%H:%M} Uhr."
    else:
        titel = f"Info: Schulessen {entry.title}"
        text = f"Für {spanne} ist alles bestellt."
    await _benachrichtigen(hass, ziele, titel, text, portal)
    return True


def _ziele(entry: ConfigEntry) -> list[str]:
    ziele = option(entry, CONF_ERINNERUNG_ZIELE) or []
    return [ziele] if isinstance(ziele, str) else list(ziele)


def ziel_link(entry: ConfigEntry) -> str | None:
    """App-Link hat Vorrang vor dem Bestellportal."""
    return (option(entry, CONF_APP_LINK) or "").strip() or option(entry, CONF_PORTAL)


async def _benachrichtigen(hass: HomeAssistant, ziele: list[str], titel: str, text: str, portal: str | None) -> None:
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


async def frist_pruefen(hass: HomeAssistant, entry: ConfigEntry, store: Store, gesendet: set[str]) -> list[str]:
    """Benachrichtigen, wenn der Bestellschluss eines offenen Tages innerhalb des Vorlaufs liegt."""
    stunden = vorlauf(entry)
    ziele = _ziele(entry)
    if not stunden or not ziele:
        return []
    jetzt = dt_util.now()
    neu = []
    for d, t in offene_tage_sync((entry.runtime_data.data or {}).get("tage")):
        s = schluss_zeit(t)
        if not s or d in gesendet or not (s - timedelta(hours=stunden) <= jetzt < s):
            continue
        rest = s - jetzt
        h, m = divmod(int(rest.total_seconds() // 60), 60)
        noch = f"{h} Std. {m} Min." if h else f"{m} Min."
        tag = "heute" if s.date() == jetzt.date() else ("morgen" if s.date() == jetzt.date() + timedelta(days=1) else _kurz(s.date().isoformat()))
        await _benachrichtigen(
            hass, ziele, f"Zu tun: Essen bestellen – {entry.title}",
            f"Für {_kurz(d)} ist noch nichts bestellt. Bestellschluss {tag} {s:%H:%M} Uhr, noch {noch}",
            ziel_link(entry))
        gesendet.add(d)
        neu.append(d)
    if neu:
        heute = jetzt.date().isoformat()
        await store.async_save(sorted(x for x in gesendet if x >= heute))
    return neu


@callback
def einrichten(hass: HomeAssistant, entry: ConfigEntry):
    """Auslöser registrieren; gibt die Abmeldefunktion zurück."""
    if not option(entry, CONF_ERINNERUNG, False):
        return None
    try:
        z = time.fromisoformat(str(option(entry, CONF_ERINNERUNG_ZEIT, STANDARD_ZEIT)))
    except ValueError:
        z = time.fromisoformat(STANDARD_ZEIT)

    async def _taeglich(_now: datetime) -> None:
        await senden(hass, entry)

    abmelden = [async_track_time_change(hass, _taeglich, hour=z.hour, minute=z.minute, second=0)]
    if vorlauf(entry):
        store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.frist")
        gesendet: set[str] = set()

        async def _laden() -> None:
            gesendet.update(await store.async_load() or [])
            await frist_pruefen(hass, entry, store, gesendet)

        async def _frist(_now: datetime) -> None:
            await frist_pruefen(hass, entry, store, gesendet)

        entry.async_create_background_task(hass, _laden(), "schulessen_frist_laden")
        abmelden.append(async_track_time_interval(hass, _frist, timedelta(minutes=5)))

    @callback
    def _alle_abmelden() -> None:
        for a in abmelden:
            a()

    return _alle_abmelden
