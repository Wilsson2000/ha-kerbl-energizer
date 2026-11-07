"""Sensors for Kerbl smart energizers.

Known fields get proper names, units and categories. Any other numeric field
the cloud sends still becomes a (disabled) sensor, so nothing is lost.
Units seen on a Duo Power Xi8000: fenceVoltage 7.5 with target 9.5 -> kV,
batteryVoltage 14 -> V, batteryState 71 / signalQuality 79 -> %.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KerblConfigEntry
from .coordinator import KerblCoordinator
from .entity import KerblEntity

KV = UnitOfElectricPotential.KILOVOLT
V = UnitOfElectricPotential.VOLT


@dataclass(frozen=True)
class Spec:
    name: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    category: EntityCategory | None = None
    enabled: bool = True
    icon: str | None = None
    measurement: bool = True


KNOWN: dict[str, Spec] = {
    "fenceVoltage": Spec("Stängselspänning", KV, SensorDeviceClass.VOLTAGE, icon="mdi:flash"),
    "fenceVoltageSecondary": Spec("Stängselspänning 2", KV, SensorDeviceClass.VOLTAGE, icon="mdi:flash"),
    "fenceVoltageTarget": Spec("Målspänning", KV, SensorDeviceClass.VOLTAGE, EntityCategory.DIAGNOSTIC, measurement=False),
    "fenceVoltageAlarmThreshold": Spec("Larmgräns spänning", KV, SensorDeviceClass.VOLTAGE, EntityCategory.DIAGNOSTIC, measurement=False),
    "fenceVoltageAlarmThresholdSecondary": Spec("Larmgräns spänning 2", KV, SensorDeviceClass.VOLTAGE, EntityCategory.DIAGNOSTIC, measurement=False),
    "batteryVoltage": Spec("Batterispänning", V, SensorDeviceClass.VOLTAGE),
    "batteryVoltageAlarmThreshold": Spec("Larmgräns batteri", V, SensorDeviceClass.VOLTAGE, EntityCategory.DIAGNOSTIC, measurement=False),
    "batteryState": Spec("Batteri", PERCENTAGE, SensorDeviceClass.BATTERY),
    "gridVoltage": Spec("Nätspänning", V, SensorDeviceClass.VOLTAGE),
    "groundVoltage": Spec("Jordspänning", KV, SensorDeviceClass.VOLTAGE),
    "solarVoltage": Spec("Solpanelspänning", V, SensorDeviceClass.VOLTAGE),
    "energyAbsorption": Spec("Energiförbrukning stängsel", icon="mdi:lightning-bolt-outline"),
    "signalQuality": Spec("Signalstyrka", PERCENTAGE, category=EntityCategory.DIAGNOSTIC, icon="mdi:signal"),
    "mode": Spec("Läge", category=EntityCategory.DIAGNOSTIC, icon="mdi:tune", measurement=False),
    "numberOfNewEvents": Spec("Nya händelser", icon="mdi:bell-alert-outline", measurement=False),
}
# Text fields worth a sensor.
TEXT: dict[str, Spec] = {
    "currentError": Spec("Felkod", category=EntityCategory.DIAGNOSTIC, icon="mdi:alert-circle-outline", measurement=False),
}
SKIP = {"id", "userId"}


def _label(key: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", key).capitalize()


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


async def async_setup_entry(hass: HomeAssistant, entry: KerblConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = []
        for device_id, data in coordinator.data.items():
            for key, value in data.items():
                uid = f"{device_id}_{key}"
                if uid in known or key in SKIP:
                    continue
                if key in KNOWN:
                    # Known fields are created even while null (e.g. solar on a mains unit stays unknown).
                    if value is None and key not in ("fenceVoltage", "batteryVoltage", "batteryState"):
                        continue
                    spec = KNOWN[key]
                elif key in TEXT:
                    spec = TEXT[key]
                elif _is_number(value):
                    spec = Spec(_label(key), enabled=False)
                else:
                    continue
                known.add(uid)
                new.append(KerblSensor(coordinator, device_id, key, spec, text=key in TEXT))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class KerblSensor(KerblEntity, SensorEntity):
    def __init__(self, coordinator: KerblCoordinator, device_id: str, key: str, spec: Spec, text: bool = False) -> None:
        super().__init__(coordinator, device_id, key)
        self._text = text
        self._attr_name = spec.name
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_entity_category = spec.category
        self._attr_entity_registry_enabled_default = spec.enabled
        if spec.icon:
            self._attr_icon = spec.icon
        if spec.measurement and not text:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        value = self.device_data.get(self._key)
        if self._text:
            return None if value is None else str(value)[:255]
        return value if _is_number(value) else None
