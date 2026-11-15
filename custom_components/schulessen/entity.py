from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class SpeiseplanEntity(CoordinatorEntity):
    """Basis: Name = '<Kind> <Bezeichnung>', damit die Entitäts-IDs kurz bleiben (z. B. sensor.anna_essen_heute)."""

    _attr_has_entity_name = False
    _bezeichnung = ""

    def __init__(self, coord, key: str) -> None:
        super().__init__(coord)
        e = coord.config_entry
        self._attr_unique_id = f"{e.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, e.unique_id)}, name=f"Schulessen {e.title}",
            manufacturer="Bestellportal", model="Speiseplan", entry_type=DeviceEntryType.SERVICE)

    @property
    def name(self) -> str:
        return f"{self.coordinator.config_entry.title} {self._bezeichnung}"
