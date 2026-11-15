from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .entity import SpeiseplanEntity
from .erinnerung import senden


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ErinnerungTesten(entry.runtime_data)])


class ErinnerungTesten(SpeiseplanEntity, ButtonEntity):
    _bezeichnung = "Essen-Erinnerung senden"
    _attr_icon = "mdi:bell-ring-outline"

    def __init__(self, c) -> None:
        super().__init__(c, "erinnerung_senden")

    async def async_press(self) -> None:
        await senden(self.hass, self.coordinator.config_entry, auch_wenn_leer=True)
