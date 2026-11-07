"""On/off switch for the energizer (Kerbl command "mode").

The web app sends PATCH .../command/mode {"value": <toggle bool>}. The cloud
forwards it to the energizer over cellular, so the real state follows a
little later; the switch shows the requested state until the next poll
confirms it, then follows 'mode' again.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KerblConfigEntry
from .api import KerblApiError, KerblAuthError
from .coordinator import KerblCoordinator
from .entity import KerblEntity

PENDING_SECONDS = 180


async def async_setup_entry(hass: HomeAssistant, entry: KerblConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(KerblPowerSwitch(coordinator, device_id) for device_id, data in coordinator.data.items() if "mode" in data)


class KerblPowerSwitch(KerblEntity, SwitchEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_name = "Stängsel"
    _attr_icon = "mdi:fence-electric"

    def __init__(self, coordinator: KerblCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "power_switch")
        self._pending: bool | None = None
        self._pending_until = 0.0

    @property
    def is_on(self) -> bool | None:
        mode = self.device_data.get("mode")
        actual = None if not isinstance(mode, (int, float)) else mode != 0
        if self._pending is not None:
            if actual == self._pending or time.monotonic() > self._pending_until:
                self._pending = None
            else:
                return self._pending
        return actual

    @property
    def available(self) -> bool:
        return super().available and bool(self.device_data.get("isOnline"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"väntar_på_aggregatet": self._pending is not None}

    async def _set(self, on: bool) -> None:
        try:
            await self.coordinator.client.send_command(self._device_id, "mode", on)
        except (KerblApiError, KerblAuthError) as err:
            raise HomeAssistantError(f"Kerbl svarade inte på kommandot: {err}") from err
        self._pending = on
        self._pending_until = time.monotonic() + PENDING_SECONDS
        self.async_write_ha_state()
        # Give the cloud a moment to reach the energizer, then poll.
        await asyncio.sleep(15)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
