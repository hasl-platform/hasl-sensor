from asyncio import timeout
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from tsl.clients.deviations import DeviationsClient
from tsl.models.common import TransportMode
from tsl.models.deviations import Deviation
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector as sel
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .. import const
from .device import SL_TRAFFIK_DEVICE_INFO

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(const.CONF_SITE_IDS): sel.TextSelector(
            sel.TextSelectorConfig(multiple=True, type=sel.TextSelectorType.NUMBER)
        ),
        vol.Optional(const.CONF_LINES): sel.TextSelector(
            sel.TextSelectorConfig(multiple=True, type=sel.TextSelectorType.NUMBER)
        ),
        vol.Optional(const.CONF_TRANSPORTS): sel.SelectSelector(
            sel.SelectSelectorConfig(
                options=[e.value for e in TransportMode],
                translation_key=const.CONF_TRANSPORT,
                multiple=True,
            )
        ),
        vol.Optional(const.CONF_SENSOR): sel.EntitySelector(
            sel.EntitySelectorConfig(domain="binary_sensor")
        ),
        vol.Required(const.CONF_SCAN_INTERVAL, default=61): sel.NumberSelector(
            sel.NumberSelectorConfig(
                min=61,
                unit_of_measurement="seconds",
                mode=sel.NumberSelectorMode.BOX,
            )
        ),
    }
)


class StatusDataUpdateCoordinator(DataUpdateCoordinator[list[Deviation]]):
    """Class to manage fetching Departure data API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""

        self._sites = entry.options.get(const.CONF_SITE_IDS)
        self._lines = entry.options.get(const.CONF_LINES)
        self._transports = entry.options.get(const.CONF_TRANSPORTS)
        self._sensor_id: str | None = entry.options.get(const.CONF_SENSOR)
        interval = timedelta(seconds=entry.options[const.CONF_SCAN_INTERVAL])

        if TYPE_CHECKING:
            assert entry.unique_id

        device_info = SL_TRAFFIK_DEVICE_INFO.copy()
        device_info["identifiers"] = {(const.DOMAIN, entry.entry_id)}
        device_info["name"] = entry.title
        self.device_info = device_info

        super().__init__(
            hass,
            logging.getLogger(__name__),
            config_entry=entry,
            name=const.DOMAIN,
            update_interval=interval,
        )

    async def _async_update_data(self):
        if self._sensor_id and not self.hass.states.is_state(self._sensor_id, STATE_ON):
            self.logger.debug(
                'Not updating %s. Sensor "%s" is off',
                self.config_entry.entry_id,
                self._sensor_id,
            )

            return self.data

        self.client = DeviationsClient(async_get_clientsession(self.hass))
        if (types := self._transports) is not None:
            transport = [TransportMode(t) for t in types]
        else:
            transport = None

        async with timeout(10):
            return await self.client.get_deviations(
                site=self._sites,
                line=self._lines,
                transport_mode=transport,
            )


class TrafikStatusSensor(CoordinatorEntity[StatusDataUpdateCoordinator], SensorEntity):
    """Trafik Status Sensor class."""

    # exclude heavy attributes from recorder
    _unrecorded_attributes = frozenset({"deviations"})

    _attr_attribution = "Stockholm Lokaltrafik"

    entity_description = SensorEntityDescription(
        key="status",
        icon="mdi:alert",
        has_entity_name=True,
        name="Deviations"
    )

    def __init__(
        self,
        entry: ConfigEntry[StatusDataUpdateCoordinator],
    ) -> None:
        """Initialize."""
        super().__init__(entry.runtime_data)

        self._attr_unique_id = f"{entry.entry_id}_{self.entity_description.key}"
        self._attr_device_info = self.coordinator.device_info

    @property
    def native_value(self) -> int | None:
        """Return the state."""

        if self.coordinator.data is None:
            return None

        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""

        if not self.coordinator.data:
            return {}

        return {"deviations": self.coordinator.data}


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the sensor platform."""

    coordinator = StatusDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # subscribe to updates
    entry.async_on_unload(entry.add_update_listener(update_listener))

    sensors = [TrafikStatusSensor(entry)]
    async_add_entities(sensors)
