from asyncio import timeout
from datetime import timedelta
import logging
from typing import NamedTuple

from aiohttp import ClientSession
from tsl.clients.deviations import DeviationsClient
from tsl.models.common import TransportMode
from tsl.models.deviations import Deviation
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector as sel
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .. import const
from .device import SL_TRAFFIK_DEVICE_INFO

logger = logging.getLogger(f"custom_components.{const.DOMAIN}.sensors.status")

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


class SettingsKey(NamedTuple):
    """Settings container."""

    sites: list[str] | None
    lines: list[str] | None
    transports: list[str] | None


class StatusDataUpdateCoordinator(DataUpdateCoordinator[list[Deviation]]):
    """Class to manage fetching Departure data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        key: SettingsKey,
        update_interval: timedelta,
        sensor_id: str | None,
    ) -> None:
        """Initialize."""
        self.key = key
        self.sensor_id = sensor_id

        self._session = session
        self.client = DeviationsClient()

        self.device_info = SL_TRAFFIK_DEVICE_INFO

        super().__init__(
            hass, logger, name=const.DOMAIN, update_interval=update_interval
        )

    async def _async_update_data(self) -> list[Deviation]:
        """Update data via library."""

        if self.sensor_id and not self.hass.states.is_state(self.sensor_id, STATE_ON):
            self.logger.debug(
                'Not updating %s. Sensor "%s" is off',
                self.config_entry.entry_id,
                self.sensor_id,
            )

            return self.data

        if (types := self.key.transports) is not None:
            transport = [TransportMode(t) for t in types]
        else:
            transport = None

        async with timeout(10):
            return await self.client.get_deviations(
                site=self.key.sites,
                line=self.key.lines,
                transport_mode=transport,
                session=self._session,
            )


class TrafikStatusSensor(CoordinatorEntity[StatusDataUpdateCoordinator], SensorEntity):
    """Trafik Status Sensor class."""

    # exclude heavy attributes from recorder
    _unrecorded_attributes = frozenset({"deviations"})

    _attr_attribution = "Stockholm Lokaltrafik"
    _attr_has_entity_name = True

    entity_description = SensorEntityDescription(
        key="status",
        icon="mdi:alert",
    )

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: StatusDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._sensor_data = coordinator.data
        self._attr_unique_id = f"{entry.entry_id}_{self.entity_description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def name(self):
        return "Deviations"

    @property
    def native_value(self) -> int | None:
        """Return the state."""

        if self._sensor_data is None:
            return None

        return len(self._sensor_data)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""

        if not self._sensor_data:
            return {}

        return {"deviations": self._sensor_data}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = self.coordinator.data
        self.async_write_ha_state()


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the sensor platform."""

    websession = async_get_clientsession(hass)
    key = SettingsKey(
        sites=entry.options.get(const.CONF_SITE_IDS),
        lines=entry.options.get(const.CONF_LINES),
        transports=entry.options.get(const.CONF_TRANSPORTS),
    )
    interval = timedelta(seconds=entry.options[const.CONF_SCAN_INTERVAL])
    sensor_id: str | None = entry.options.get(const.CONF_SENSOR)

    coordinator = StatusDataUpdateCoordinator(
        hass, websession, key, interval, sensor_id
    )
    await coordinator.async_config_entry_first_refresh()

    # subscribe to updates
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # TODO: use manager to store coordinators
    hass.data.setdefault(const.DOMAIN, {})[entry.entry_id] = coordinator

    sensors = [TrafikStatusSensor(entry, coordinator)]
    async_add_entities(sensors)
