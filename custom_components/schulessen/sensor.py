from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_ERINNERUNG, CONF_PORTAL
from .erinnerung import offene_tage_sync, option, schluss_zeit, zeitraum
from .entity import SpeiseplanEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([EssenTag(c, 0), EssenTag(c, 1), NaechstesEssen(c), Stand(c), Bestellschluss(c)])


def _status(tag):
    if tag is None:
        return "kein Speiseplan"
    if tag["feiertag"]:
        return "Feiertag"
    if tag["zustellpause"]:
        return "abbestellt"
    if tag["bestellt"]:
        return tag["bestellt"]["name"]
    return "nicht bestellt"


def _attrs(tag, c):
    if tag is None:
        return {"datum": None, "essen": None, "menue": None, "preis": None, "kennzeichnung": None, "pause_grund": None, "bestellschluss": None, "angebot": [], "stand": c.stand, "live": c.live}
    b = tag["bestellt"]
    return {
        "datum": tag["datum"],
        "essen": b["text"] if b else None,
        "menue": b["name"] if b else None,
        "preis": b["preis"] if b else None,
        "kennzeichnung": b["kennzeichnung"] if b else None,
        "pause_grund": tag["pause_grund"] or None,
        "bestellschluss": tag["bestellschluss"],
        "angebot": [{"name": m["name"], "text": m["text"], "preis": m["preis"],
                     "bestellt": m["bestellt"]} for m in tag["menues"]],
        "stand": c.stand,
        "live": c.live,
    }


def _einrichtung(e):
    if isinstance(e, dict):
        for k in ("name", "bezeichnung", "kurzBez", "kurzbezeichnung"):
            if e.get(k):
                return str(e[k])
        return None
    return str(e) if e else None


def _tage_liste(c):
    heute = dt_util.now().date().isoformat()
    out = []
    for d, t in sorted((c.data or {}).get("tage", {}).items()):
        if d < heute:
            continue
        out.append({
            "datum": d,
            "status": _status(t),
            "feiertag": bool(t.get("feiertag")),
            "pause": bool(t.get("zustellpause")),
            "pause_grund": t.get("pause_grund") or None,
            "bestellschluss": t.get("bestellschluss"),
            "menues": [{"name": m.get("name"), "kurz": m.get("kurz") or None, "text": m.get("text"),
                        "preis": m.get("preis"), "kennzeichnung": m.get("kennzeichnung") or None,
                        "bestellt": bool(m.get("bestellt"))} for m in t.get("menues") or []],
        })
    return out


class EssenTag(SpeiseplanEntity, SensorEntity):
    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, c, offset: int) -> None:
        super().__init__(c, f"essen_{offset}")
        self._off = offset
        self._bezeichnung = "Essen heute" if offset == 0 else "Essen morgen"

    def _tag(self):
        d = (dt_util.now().date() + timedelta(days=self._off)).isoformat()
        return (self.coordinator.data or {}).get("tage", {}).get(d)

    @property
    def native_value(self):
        return _status(self._tag())

    @property
    def extra_state_attributes(self):
        return _attrs(self._tag(), self.coordinator)


class NaechstesEssen(SpeiseplanEntity, SensorEntity):
    _attr_icon = "mdi:food"
    _bezeichnung = "Essen nächster Schultag"

    def __init__(self, c) -> None:
        super().__init__(c, "naechster")

    def _tag(self):
        heute = dt_util.now().date().isoformat()
        for d, t in sorted((self.coordinator.data or {}).get("tage", {}).items()):
            if d > heute and t["menues"] and not t["feiertag"]:
                return t
        return None

    @property
    def native_value(self):
        return _status(self._tag())

    @property
    def extra_state_attributes(self):
        tage = (self.coordinator.data or {}).get("tage", {})
        heute = dt_util.now().date().isoformat()
        offen = [d for d, t in sorted(tage.items())
                 if d > heute and t["menues"] and not t["feiertag"]
                 and not t["zustellpause"] and not t["bestellt"]]
        a = _attrs(self._tag(), self.coordinator)
        a["nicht_bestellt"] = offen
        a["einrichtung"] = (self.coordinator.data or {}).get("einrichtung")
        return a


class Stand(SpeiseplanEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _bezeichnung = "Essen Stand"
    _attr_icon = "mdi:cloud-check-outline"

    def __init__(self, c) -> None:
        super().__init__(c, "stand")

    @property
    def native_value(self):
        return dt_util.parse_datetime(self.coordinator.stand) if self.coordinator.stand else None

    _unrecorded_attributes = frozenset({"tage", "einrichtung", "portal", "kind", "schulessen_karte"})

    @property
    def extra_state_attributes(self):
        c = self.coordinator
        e = c.config_entry
        return {
            "live": c.live,
            "schulessen_karte": True,
            "kind": e.title,
            "einrichtung": _einrichtung((c.data or {}).get("einrichtung")),
            "portal": e.options.get(CONF_PORTAL, e.data.get(CONF_PORTAL)) or None,
            "hinweis_tage": zeitraum(e),
            "erinnerung": bool(option(e, CONF_ERINNERUNG, False)),
            "tage": _tage_liste(c),
        }


class Bestellschluss(SpeiseplanEntity, SensorEntity):
    """Nächster Bestellschluss eines Tages ohne Bestellung."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-sand"
    _bezeichnung = "Nächster Bestellschluss"

    def __init__(self, c) -> None:
        super().__init__(c, "bestellschluss")

    def _naechster(self):
        for d, t in offene_tage_sync((self.coordinator.data or {}).get("tage")):
            if (s := schluss_zeit(t)) is not None:
                return d, s
        return None, None

    @property
    def native_value(self):
        return self._naechster()[1]

    @property
    def extra_state_attributes(self):
        return {"datum": self._naechster()[0]}
