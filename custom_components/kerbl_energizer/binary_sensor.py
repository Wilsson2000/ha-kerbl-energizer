"""Binary sensors for Kerbl smart energizers."""
from __future__ import annotations

from dataclasses import dataclass
import re

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KerblConfigEntry
from .coordinator import KerblCoordinator
from .entity import KerblEntity


@dataclass(frozen=True)
class Spec:
    name: str
    device_class: BinarySensorDeviceClass | None = None
    category: EntityCategory | None = None
    enabled: bool = True
    icon: str | None = None


KNOWN: dict[str, Spec] = {
    "isOnline": Spec("Uppkopplad", BinarySensorDeviceClass.CONNECTIVITY, EntityCategory.DIAGNOSTIC),
    "active": Spec("Aktiverad i kontot", category=EntityCategory.DIAGNOSTIC),
    "doDesiredAndActualStateMatch": Spec("Inställningar synkade", category=EntityCategory.DIAGNOSTIC, icon="mdi:sync"),
    "pushNotifications": Spec("Push-notiser i appen", category=EntityCategory.DIAGNOSTIC, enabled=False),
    "emailNotifications": Spec("E-postnotiser i appen", category=EntityCategory.DIAGNOSTIC, enabled=False),
}


def _label(key: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", key).capitalize()


async def async_setup_entry(hass: HomeAssistant, entry: KerblConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = []
        for device_id, data in coordinator.data.items():
            run_uid = f"{device_id}_running"
            if run_uid not in known and "mode" in data:
                known.add(run_uid)
                new.append(KerblRunning(coordinator, device_id))
            low_uid = f"{device_id}_low_fence_voltage"
            if low_uid not in known and "fenceVoltage" in data:
                known.add(low_uid)
                new.append(KerblLowVoltage(coordinator, device_id))
            for key, value in data.items():
                uid = f"{device_id}_{key}"
                if uid in known or not isinstance(value, bool):
                    continue
                known.add(uid)
                spec = KNOWN.get(key, Spec(_label(key), enabled=False))
                new.append(KerblBoolSensor(coordinator, device_id, key, spec))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class KerblBoolSensor(KerblEntity, BinarySensorEntity):
    def __init__(self, coordinator: KerblCoordinator, device_id: str, key: str, spec: Spec) -> None:
        super().__init__(coordinator, device_id, key)
        self._attr_name = spec.name
        self._attr_device_class = spec.device_class
        self._attr_entity_category = spec.category
        self._attr_entity_registry_enabled_default = spec.enabled
        if spec.icon:
            self._attr_icon = spec.icon

    @property
    def is_on(self) -> bool | None:
        value = self.device_data.get(self._key)
        return value if isinstance(value, bool) else None


class KerblLowVoltage(KerblEntity, BinarySensorEntity):
    """On when fence voltage is below the alarm threshold set in the app."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Låg stängselspänning"

    def __init__(self, coordinator: KerblCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "low_fence_voltage")

    @property
    def is_on(self) -> bool | None:
        data = self.device_data
        volt, limit = data.get("fenceVoltage"), data.get("fenceVoltageAlarmThreshold")
        if not isinstance(volt, (int, float)) or not isinstance(limit, (int, float)):
            return None
        return volt < limit

    @property
    def extra_state_attributes(self):
        data = self.device_data
        return {"stangselspanning_kv": data.get("fenceVoltage"), "larmgrans_kv": data.get("fenceVoltageAlarmThreshold")}


class KerblRunning(KerblEntity, BinarySensorEntity):
    """On while the energizer is pulsing.

    Seen on a Duo Power Xi8000: switching off in the app sets mode 1 -> 0,
    fenceVoltage -> 0 and adds 8 to currentError, while 'active' stays true.
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_name = "Igång"
    _attr_icon = "mdi:fence-electric"

    def __init__(self, coordinator: KerblCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "running")

    @property
    def is_on(self) -> bool | None:
        mode = self.device_data.get("mode")
        if not isinstance(mode, (int, float)) or isinstance(mode, bool):
            return None
        return mode != 0
