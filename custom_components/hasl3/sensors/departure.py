"""Departure sensor for hasl3."""

from asyncio import timeout
from datetime import timedelta
from enum import StrEnum
import logging
import math
from typing import Any, NamedTuple

from aiohttp import ClientSession
from tsl.clients.transport import TransportClient
from tsl.models.departures import SiteDepartureResponse, TransportMode
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
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
from homeassistant.util.dt import now

from .. import const
from .device import SL_TRAFFIK_DEVICE_INFO

logger = logging.getLogger(f"custom_components.{const.DOMAIN}.sensors.departure")


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(const.CONF_SITE_ID): sel.NumberSelector(
            sel.NumberSelectorConfig(min=0, mode=sel.NumberSelectorMode.BOX)
        ),
        vol.Optional(const.CONF_TRANSPORT): sel.SelectSelector(
            sel.SelectSelectorConfig(
                options=[e.value for e in TransportMode],
                translation_key=const.CONF_TRANSPORT,
            )
        ),
        vol.Optional(const.CONF_LINE): sel.NumberSelector(
            sel.NumberSelectorConfig(min=0, mode=sel.NumberSelectorMode.BOX)
        ),
        vol.Optional(
            const.CONF_DIRECTION, default=str(const.DirectionType.ANY.value)
        ): sel.SelectSelector(
            sel.SelectSelectorConfig(
                options=[str(e.value) for e in const.DirectionType],
                translation_key=const.CONF_DIRECTION,
            )
        ),
        vol.Optional(const.CONF_TIMEWINDOW, default=60): sel.NumberSelector(
            sel.NumberSelectorConfig(
                min=5,
                max=60,
                unit_of_measurement="minutes",
                mode=sel.NumberSelectorMode.SLIDER,
            )
        ),
        vol.Optional(const.CONF_SENSOR): sel.EntitySelector(
            sel.EntitySelectorConfig(domain="binary_sensor")
        ),
        vol.Required(const.CONF_SCAN_INTERVAL, default=60): sel.NumberSelector(
            sel.NumberSelectorConfig(
                min=0,
                unit_of_measurement="seconds",
                mode=sel.NumberSelectorMode.BOX,
            )
        ),
    }
)


class DepartureKey(NamedTuple):
    """DepartureKey."""

    siteid: int
    transport: str | None
    direction: int | None
    forecast: int | None
    line: int | None


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

    def _int_or_none(v) -> None | int:
        if v is None:
            return v

        return int(v) or None

    key = DepartureKey(
        siteid=int(entry.options[const.CONF_SITE_ID]),
        transport=entry.options.get(const.CONF_TRANSPORT) or None,
        direction=_int_or_none(entry.options.get(const.CONF_DIRECTION)),
        forecast=_int_or_none(entry.options.get(const.CONF_TIMEWINDOW)),
        line=_int_or_none(entry.options.get(const.CONF_LINE)),
    )
    interval = timedelta(seconds=entry.options[const.CONF_SCAN_INTERVAL])
    sensor_id: str | None = entry.options.get(const.CONF_SENSOR)

    coordinator = DepartureDataUpdateCoordinator(
        hass, websession, key, interval, sensor_id
    )
    await coordinator.async_config_entry_first_refresh()

    # subscribe to updates
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # TODO: use manager to store coordinators
    hass.data.setdefault(const.DOMAIN, {})[entry.entry_id] = coordinator

    sensors = [
        TrafikDepartureSensor(entry, coordinator, description)
        for description in DEPARTURE_SENSORS
    ]

    async_add_entities(sensors)


class DepartureDataUpdateCoordinator(DataUpdateCoordinator[SiteDepartureResponse]):
    """Class to manage fetching Departure data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        key: DepartureKey,
        update_interval: timedelta,
        sensor_id: str | None,
    ) -> None:
        """Initialize."""
        self.key = key
        self.sensor_id = sensor_id

        self._session = session
        self.client = TransportClient()

        self.device_info = SL_TRAFFIK_DEVICE_INFO

        super().__init__(
            hass, logger, name=const.DOMAIN, update_interval=update_interval
        )

    async def _async_update_data(self) -> SiteDepartureResponse:
        """Update data via library."""

        if self.sensor_id and not self.hass.states.is_state(self.sensor_id, STATE_ON):
            self.logger.debug(
                'Not updating %s. Sensor "%s" is off',
                self.config_entry.entry_id,
                self.sensor_id,
            )

            return self.data

        transport = TransportMode(self.key.transport) if self.key.transport else None
        async with timeout(10):
            return await self.client.get_site_departures(
                self.key.siteid,
                transport=transport,
                direction=self.key.direction,
                line=self.key.line,
                forecast=self.key.forecast,
                session=self._session,
            )


class SensorEntityType(StrEnum):
    """SensorEntityType type."""

    DEPARTURES = "departures"
    DEVIATIONS = "deviations"
    MINIMUM = "min"
    TIME = "time"


DEPARTURE_SENSORS = (
    # main sensor. contains 'departures' attribute with raw data
    SensorEntityDescription(
        key=SensorEntityType.DEPARTURES,
        icon="mdi:train",
    ),
    # secondary sensor. contains 'deviations' attribute with raw data
    SensorEntityDescription(
        key=SensorEntityType.DEVIATIONS,
        icon="mdi:alert",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=SensorEntityType.MINIMUM,
        icon="mdi:clock",
        native_unit_of_measurement="min",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=SensorEntityType.TIME,
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
)


class TrafikDepartureSensor(
    CoordinatorEntity[DepartureDataUpdateCoordinator], SensorEntity
):
    """Trafik Departure Sensor class."""

    # exclude heavy attributes from recorder
    _unrecorded_attributes = frozenset({"departures", "deviations"})

    _attr_attribution = "Stockholm Lokaltrafik"
    _attr_has_entity_name = True

    entity_description: SensorEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DepartureDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.entity_description = description
        self._sensor_data = coordinator.data

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    def _nextDeparture(self):
        if not self._sensor_data:
            return None

        departures = sorted(
            self._sensor_data.departures, key=lambda x: x.expected or x.scheduled
        )
        return next(iter(departures), None)

    @property
    def name(self):
        if self.entity_description.key == SensorEntityType.DEPARTURES:
            return "Departures"
        elif self.entity_description.key == SensorEntityType.DEVIATIONS:
            return "Stop deviations"
        elif self.entity_description.key == SensorEntityType.MINIMUM:
            return "Next Departure in"
        elif self.entity_description.key == SensorEntityType.TIME:
            return "Next Departure at"

        return super().name

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""

        if not self._sensor_data:
            return None

        if self.entity_description.key == SensorEntityType.DEPARTURES:
            return len(self._sensor_data.departures)
        elif self.entity_description.key == SensorEntityType.DEVIATIONS:
            return len(self._sensor_data.stop_deviations)

        if not self._sensor_data:
            return None

        if (departure := self._nextDeparture()) is None:
            return None

        time = departure.expected or departure.scheduled
        if self.entity_description.key == SensorEntityType.MINIMUM:
            delta = time - now()
            expected_minutes = math.floor(delta.total_seconds() / 60)
            return str(max(0, expected_minutes))

        elif self.entity_description.key == SensorEntityType.TIME:
            return time

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""

        if not self._sensor_data:
            return {}

        # only report extented attributes for main "departures" sensor
        if self.entity_description.key == SensorEntityType.DEPARTURES:
            return {"departures": self._sensor_data.departures}

        elif self.entity_description.key == SensorEntityType.DEVIATIONS:
            return {"deviations": self._sensor_data.stop_deviations}

        return {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = self.coordinator.data
        self.async_write_ha_state()
