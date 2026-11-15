from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.util import dt as dt_util

from .entity import SpeiseplanEntity
from .erinnerung import offene_tage_sync, schluss_zeit, zeitraum


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EssenOffen(entry.runtime_data)])


class EssenOffen(SpeiseplanEntity, BinarySensorEntity):
    """An, wenn im Erinnerungszeitraum ein Schultag ohne Bestellung liegt (Ferienkalender nicht berücksichtigt)."""

    _attr_icon = "mdi:food-off-outline"
    _bezeichnung = "Essen offen"

    def __init__(self, c) -> None:
        super().__init__(c, "offen")

    def _offen(self):
        e = self.coordinator.config_entry
        bis = dt_util.now().date() + timedelta(days=zeitraum(e))
        heute = dt_util.now().date().isoformat()
        return [(d, t) for d, t in offene_tage_sync((self.coordinator.data or {}).get("tage"), bis) if d > heute]

    @property
    def is_on(self):
        return bool(self._offen())

    @property
    def extra_state_attributes(self):
        offen = self._offen()
        s = schluss_zeit(offen[0][1]) if offen else None
        return {"tage": [d for d, _ in offen], "naechster_bestellschluss": s.isoformat() if s else None,
                "zeitraum_tage": zeitraum(self.coordinator.config_entry)}
