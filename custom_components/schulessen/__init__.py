"""Schulessen: Speiseplan und Bestellstatus aus Schulessen-Bestellportalen."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import erinnerung
from .api_rest import RestAuthError, RestClient
from .api_wamp import WampAuthError, WampClient
from .const import (
    CONF_MANDANT, CONF_REALM, CONF_TYP, DOMAIN, TAGE_VORAUS, TYP_REST, TYP_WAMP, WOCHEN,
)
from .dashboard import async_dashboard_einrichten, async_karte_registrieren

AUTH_FEHLER_GRENZE = 3

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.BUTTON]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def client_fuer(hass: HomeAssistant, d: dict):
    s = async_get_clientsession(hass)
    if d.get(CONF_TYP) == TYP_REST:
        return RestClient(s, d[CONF_URL], d[CONF_MANDANT], d[CONF_USERNAME], d[CONF_PASSWORD])
    return WampClient(s, d[CONF_URL], d[CONF_REALM], d[CONF_USERNAME], d[CONF_PASSWORD])


class SpeiseplanCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(hours=1))
        self.typ = entry.data.get(CONF_TYP, TYP_WAMP)
        self.client = client_fuer(hass, entry.data)
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.live = True
        self.stand = None
        self.auth_fehler = 0
        self.ausnahmen: set[str] = set()
        self.ausnahmen_store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.ausnahmen")

    async def ausnahmen_laden(self) -> None:
        self.ausnahmen = set(await self.ausnahmen_store.async_load() or [])

    def markieren(self, data):
        """Tage ohne gewünschtes Essen kennzeichnen."""
        for d, t in ((data or {}).get("tage") or {}).items():
            t["ausgenommen"] = d in self.ausnahmen
        return data

    async def ausnahme_setzen(self, tage: list[str], aktiv: bool) -> None:
        heute = dt_util.now().date().isoformat()
        if aktiv:
            self.ausnahmen.update(tage)
        else:
            self.ausnahmen.difference_update(tage)
        self.ausnahmen = {d for d in self.ausnahmen if d >= heute}
        await self.ausnahmen_store.async_save(sorted(self.ausnahmen))
        self.markieren(self.data)
        self.async_update_listeners()

    async def _abrufen(self):
        if self.typ == TYP_REST:
            heute = dt_util.now().date()
            return await self.client.fetch(heute - timedelta(days=1), heute + timedelta(days=TAGE_VORAUS))
        return await self.client.fetch(WOCHEN)

    async def _async_update_data(self):
        try:
            async with asyncio.timeout(180):
                data = await self._abrufen()
        except (WampAuthError, RestAuthError) as err:
            # Anbieter lehnen Logins gelegentlich kurz ab (Wartung, Überlast).
            # Erst nach mehreren Fehlversuchen in Folge neu anmelden lassen.
            self.auth_fehler += 1
            if self.auth_fehler >= AUTH_FEHLER_GRENZE:
                raise ConfigEntryAuthFailed(str(err)) from err
            _LOGGER.warning(
                "Anmeldung abgelehnt (%s/%s): %s", self.auth_fehler, AUTH_FEHLER_GRENZE, err
            )
            return await self._zwischenspeicher(err)
        except Exception as err:  # noqa: BLE001
            return await self._zwischenspeicher(err)
        self.auth_fehler = 0
        self.live = True
        self.stand = dt_util.now().isoformat()
        await self.store.async_save({"stand": self.stand, "data": data})
        return self.markieren(data)

    async def _zwischenspeicher(self, err: Exception):
        alt = await self.store.async_load()
        if alt:
            _LOGGER.warning("Speiseplan nicht erreichbar, nutze Zwischenspeicher: %s", repr(err))
            _LOGGER.debug("Fehler beim Abruf", exc_info=True)
            self.live = False
            self.stand = alt.get("stand")
            return self.markieren(alt["data"])
        raise UpdateFailed(str(err)) from err


SERVICE_KEIN_ESSEN = "kein_essen"
SCHEMA_KEIN_ESSEN = vol.Schema({
    vol.Required("entity_id"): cv.entity_ids,
    vol.Required("datum"): cv.date,
    vol.Optional("bis"): cv.date,
    vol.Optional("aktiv", default=True): cv.boolean,
})


async def async_setup(hass: HomeAssistant, config) -> bool:
    async def _kein_essen(call: ServiceCall) -> None:
        reg = er.async_get(hass)
        von, bis = call.data["datum"], call.data.get("bis") or call.data["datum"]
        if bis < von:
            raise ServiceValidationError("bis liegt vor datum")
        tage, d = [], von
        while d <= bis:
            tage.append(d.isoformat())
            d += timedelta(days=1)
        eintraege = set()
        for eid in call.data["entity_id"]:
            e = reg.async_get(eid)
            if e and e.platform == DOMAIN and e.config_entry_id:
                eintraege.add(e.config_entry_id)
        if not eintraege:
            raise ServiceValidationError("Keine Schulessen-Entität angegeben")
        for entry_id in eintraege:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry and getattr(entry, "runtime_data", None):
                await entry.runtime_data.ausnahme_setzen(tage, call.data["aktiv"])

    hass.services.async_register(DOMAIN, SERVICE_KEIN_ESSEN, _kein_essen, schema=SCHEMA_KEIN_ESSEN)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coord = SpeiseplanCoordinator(hass, entry)
    await coord.ausnahmen_laden()
    await coord.async_config_entry_first_refresh()
    entry.runtime_data = coord
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_karte_registrieren(hass)
    coord.optionen = dict(entry.options)
    entry.async_on_unload(entry.add_update_listener(_optionen_geaendert))
    hass.async_create_task(async_dashboard_einrichten(hass, entry))
    if (abmelden := erinnerung.einrichten(hass, entry)) is not None:
        entry.async_on_unload(abmelden)
    return True


async def _optionen_geaendert(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coord = entry.runtime_data
    if dict(entry.options) != getattr(coord, "optionen", None):
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
