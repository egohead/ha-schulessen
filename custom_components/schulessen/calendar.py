from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .entity import SpeiseplanEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SpeiseplanKalender(entry.runtime_data)])


class SpeiseplanKalender(SpeiseplanEntity, CalendarEntity):
    _bezeichnung = "Speiseplan"
    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, c) -> None:
        super().__init__(c, "kalender")

    def _events(self) -> list[CalendarEvent]:
        out = []
        for d, t in sorted((self.coordinator.data or {}).get("tage", {}).items()):
            if not t["menues"] or t["feiertag"]:
                continue
            day = date.fromisoformat(d)
            b = t["bestellt"]
            if t["zustellpause"]:
                summary = f"Kein Essen ({t['pause_grund'] or 'abbestellt'})"
            elif b:
                summary = f"{b['name']}: {b['text']}"
            else:
                summary = "Essen nicht bestellt"
            desc = "\n".join(f"{'✓ ' if m['bestellt'] else ''}{m['name']} ({m['preis']:.2f} €): {m['text']}"
                             if m["preis"] is not None else f"{m['name']}: {m['text']}" for m in t["menues"])
            out.append(CalendarEvent(start=day, end=day + timedelta(days=1),
                                     summary=summary, description=desc))
        return out

    @property
    def event(self) -> CalendarEvent | None:
        heute = dt_util.now().date()
        for e in self._events():
            if e.start >= heute:
                return e
        return None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime):
        s, e = start_date.date(), end_date.date()
        return [ev for ev in self._events() if ev.start < e and ev.end > s]
