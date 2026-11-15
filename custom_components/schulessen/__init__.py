"""Schulessen: Speiseplan und Bestellstatus aus Schulessen-Bestellportalen."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
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

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.CALENDAR, Platform.BUTTON]
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
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            alt = await self.store.async_load()
            if alt:
                _LOGGER.warning("Speiseplan nicht erreichbar, nutze Zwischenspeicher: %s", err)
                self.live = False
                self.stand = alt.get("stand")
                return alt["data"]
            raise UpdateFailed(str(err)) from err
        self.live = True
        self.stand = dt_util.now().isoformat()
        await self.store.async_save({"stand": self.stand, "data": data})
        return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coord = SpeiseplanCoordinator(hass, entry)
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
