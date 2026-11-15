"""Diagnose-Export ohne Zugangsdaten."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_ERINNERUNG_ZIELE

SCHWAERZEN = {CONF_PASSWORD, CONF_USERNAME, "bestellerId", "kundennummer", "email", "vorname", "nachname", CONF_ERINNERUNG_ZIELE}


def _tag_kurz(t: dict) -> dict:
    return {
        "feiertag": bool(t.get("feiertag")),
        "zustellpause": bool(t.get("zustellpause")),
        "bestellt": bool(t.get("bestellt")),
        "bestellschluss": t.get("bestellschluss"),
        "menues": len(t.get("menues") or []),
    }


async def async_get_config_entry_diagnostics(hass, entry) -> dict:
    c = entry.runtime_data
    daten = c.data or {}
    return {
        "eintrag": {"title": entry.title, "version": entry.version,
                    "data": async_redact_data(dict(entry.data), SCHWAERZEN),
                    "options": async_redact_data(dict(entry.options), SCHWAERZEN)},
        "abruf": {"typ": c.typ, "live": c.live, "stand": c.stand,
                  "letzter_erfolg": c.last_update_success,
                  "fehler": str(c.last_exception) if c.last_exception else None},
        "tage": {d: _tag_kurz(t) for d, t in sorted((daten.get("tage") or {}).items())},
    }
