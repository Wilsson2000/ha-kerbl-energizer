"""Kerbl Smart Energizer (AKO) via the Kerbl Welt cloud."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
import voluptuous as vol
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KerblClient
from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import KerblCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type KerblConfigEntry = ConfigEntry[KerblCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KerblConfigEntry) -> bool:
    client = KerblClient(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_ACCESS_TOKEN),
        entry.data.get(CONF_REFRESH_TOKEN),
    )
    coordinator = KerblCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, "api_get"):
        async def _api_get(call: ServiceCall) -> ServiceResponse:
            """Read-only GET against the Kerbl API, for working out the energizer API."""
            path = "/" + call.data["path"].lstrip("/")
            entries = hass.config_entries.async_loaded_entries(DOMAIN)
            if not entries:
                return {"error": "no loaded entry"}
            client = entries[0].runtime_data.client
            try:
                result = await client._get(path)
            except Exception as err:  # noqa: BLE001 - debug tool, report everything
                return {"error": str(err)}
            return {"result": result if isinstance(result, dict) else {"list": result}}

        hass.services.async_register(
            DOMAIN,
            "api_get",
            _api_get,
            schema=vol.Schema({vol.Required("path"): str}),
            supports_response=SupportsResponse.ONLY,
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KerblConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
