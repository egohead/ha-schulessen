"""Karte registrieren und optional ein Dashboard „Schulessen“ anlegen."""
from __future__ import annotations

import inspect
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import CONF_DASHBOARD, DASHBOARD_ANGELEGT, DOMAIN

_LOGGER = logging.getLogger(__name__)

KARTE = "schulessen-card.js"
KARTE_VERSION = "1.4.0"
DASHBOARD_URL = "schulessen"


async def async_karte_registrieren(hass: HomeAssistant) -> None:
    """Die mitgelieferte Karte einmal pro Integration bereitstellen."""
    key = f"{DOMAIN}_karte"
    if hass.data.get(key):
        return
    hass.data[key] = True
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    url = f"/{DOMAIN}_karte/{KARTE}"
    pfad = Path(__file__).parent / "www" / KARTE
    await hass.http.async_register_static_paths([StaticPathConfig(url, str(pfad), False)])
    add_extra_js_url(hass, f"{url}?v={KARTE_VERSION}")


def _dashboards_collection(hass: HomeAssistant):
    handler = (hass.data.get("websocket_api") or {}).get("lovelace/dashboards/list")
    if not handler:
        return None
    owner = getattr(inspect.unwrap(handler[0]), "__self__", None)
    return getattr(owner, "storage_collection", None)


def _karte(entity: str, variante: str) -> dict:
    return {"type": "custom:schulessen-card", "entity": entity, "variante": variante}


async def async_dashboard_einrichten(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Dashboard anlegen bzw. um eine Ansicht für dieses Konto ergänzen."""
    if not entry.options.get(CONF_DASHBOARD, entry.data.get(CONF_DASHBOARD)):
        return
    if entry.data.get(DASHBOARD_ANGELEGT):
        return
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA, ConfigNotFound
    except ImportError:
        _LOGGER.warning("Dashboard konnte nicht angelegt werden: Lovelace nicht verfügbar")
        return

    reg = er.async_get(hass)
    stand = reg.async_get_entity_id("sensor", DOMAIN, f"{entry.unique_id}_stand")
    kalender = reg.async_get_entity_id("calendar", DOMAIN, f"{entry.unique_id}_kalender")
    if not stand:
        _LOGGER.warning("Dashboard: Stand-Sensor nicht gefunden")
        return

    ll = hass.data.get(LOVELACE_DATA)
    if ll is None:
        _LOGGER.warning("Dashboard konnte nicht angelegt werden: Lovelace nicht geladen")
        return
    if DASHBOARD_URL not in ll.dashboards:
        coll = _dashboards_collection(hass)
        if coll is None:
            _LOGGER.warning("Dashboard konnte nicht angelegt werden: Dashboard-Verwaltung nicht erreichbar")
            return
        await coll.async_create_item({
            "url_path": DASHBOARD_URL,
            "allow_single_word": True,
            "title": "Schulessen",
            "icon": "mdi:silverware-fork-knife",
            "show_in_sidebar": True,
            "require_admin": False,
        })
    store = ll.dashboards.get(DASHBOARD_URL)
    if store is None:
        _LOGGER.warning("Dashboard konnte nicht angelegt werden")
        return
    try:
        cfg = await store.async_load(False)
    except ConfigNotFound:
        cfg = {}
    cfg = dict(cfg or {})
    views = list(cfg.get("views") or [])

    # Übersicht mit kompakten Karten aller Kinder
    uebersicht = next((v for v in views if v.get("path") == "uebersicht"), None)
    if uebersicht is None:
        uebersicht = {"title": "Übersicht", "path": "uebersicht", "icon": "mdi:silverware-fork-knife",
                      "type": "sections", "max_columns": 2, "sections": []}
        views.insert(0, uebersicht)
    sektionen = uebersicht.setdefault("sections", [])
    vorhanden = [c.get("entity") for s in sektionen for c in s.get("cards", [])]
    if stand not in vorhanden:
        sektionen.append({"type": "grid", "cards": [_karte(stand, "kompakt")]})

    # Eigene Ansicht pro Kind mit allen Funktionen
    pfad = slugify(entry.title) or entry.entry_id[:8]
    if not any(v.get("path") == pfad for v in views):
        karten = [{"type": "grid", "column_span": 2, "cards": [_karte(stand, "voll")]}]
        if kalender:
            karten.append({"type": "grid", "cards": [
                {"type": "heading", "heading": "Kalender", "heading_style": "title", "icon": "mdi:calendar-month"},
                {"type": "calendar", "entities": [kalender], "initial_view": "listWeek"},
            ]})
        views.append({"title": entry.title, "path": pfad, "icon": "mdi:account-school",
                      "type": "sections", "max_columns": 3, "sections": karten})

    cfg["views"] = views
    await store.async_save(cfg)
    hass.config_entries.async_update_entry(entry, data={**entry.data, DASHBOARD_ANGELEGT: True})
    _LOGGER.info("Dashboard „Schulessen“ für %s eingerichtet", entry.title)
