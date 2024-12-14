"""Departure sensor for hasl3."""

from asyncio import timeout
from datetime import timedelta
import logging

from tsl.clients.transport import TransportClient
from tsl.models.departures import SiteDepartureResponse, TransportMode
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory
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


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the sensor platform."""

    coordinator = DepartureDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # subscribe to updates
    entry.async_on_unload(entry.add_update_listener(update_listener))

    sensors = [
        DeparturesSensor(entry, coordinator),
        DeviationsSensor(entry, coordinator),
        NextDepartureSensor(entry, coordinator),
    ]

    async_add_entities(sensors)


class DepartureDataUpdateCoordinator(DataUpdateCoordinator[SiteDepartureResponse]):
    """Class to manage fetching Departure data API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:

        def _int_or_none(x):
            return int(x) if x else None

        self._siteid = int(config_entry.options[const.CONF_SITE_ID])

        if transport := config_entry.options.get(const.CONF_TRANSPORT):
            self._transport = TransportMode(transport)
        else:
            self._transport = None

        if direction := _int_or_none(config_entry.options.get(const.CONF_DIRECTION)):
            self._direction = const.DirectionType(direction)
        else:
            self._direction = None

        self._forecast = (
            _int_or_none(config_entry.options.get(const.CONF_TIMEWINDOW)) or 60
        )
        self._line = _int_or_none(config_entry.options.get(const.CONF_LINE))
        self._sensor_id: str | None = config_entry.options.get(const.CONF_SENSOR)
        interval = timedelta(seconds=config_entry.options[const.CONF_SCAN_INTERVAL])

        self.device_info = SL_TRAFFIK_DEVICE_INFO

        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            config_entry=config_entry,
            name=const.DOMAIN,
            update_interval=interval,
        )

    async def _async_update_data(self) -> SiteDepartureResponse:
        """Update data via library."""

        if self._sensor_id and not self.hass.states.is_state(self._sensor_id, STATE_ON):
            self.logger.debug(
                'Not updating %s. Sensor "%s" is off',
                self.config_entry.entry_id,
                self._sensor_id,
            )

            return self.data

        client = TransportClient(async_get_clientsession(self.hass))
        async with timeout(10):
            data = await client.get_site_departures(
                self._siteid,
                transport=self._transport,
                direction=self._direction.value if self._direction else None,
                line=self._line,
                forecast=self._forecast,
            )
            return data


class BaseDepartureSensor(
    CoordinatorEntity[DepartureDataUpdateCoordinator],
    SensorEntity,
):
    _attr_attribution = "Stockholm Lokaltrafik"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DepartureDataUpdateCoordinator,
    ):
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.unique_id}_{self.entity_description.key}"
        self._attr_device_info = coordinator.device_info

    def _next_departure(self):
        if not self.coordinator.data:
            return None

        departures = sorted(
            self.coordinator.data.departures, key=lambda x: x.expected or x.scheduled
        )
        return next(iter(departures), None)


class DeparturesSensor(BaseDepartureSensor):
    _unrecorded_attributes = frozenset({"departures"})

    entity_description = SensorEntityDescription(
        key="departures",
        icon="mdi:train",
        has_entity_name=True,
        name="Departures",
    )

    @property
    def native_value(self):
        """Return the state."""

        if not self.coordinator.data:
            return None

        return len(self.coordinator.data.departures)


    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}

        return {"departures": self.coordinator.data.departures}


class DeviationsSensor(BaseDepartureSensor):

    entity_description = SensorEntityDescription(
        key="deviations",
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
        name="Stop deviations",
        entity_registry_enabled_default=False,
    )

    _unrecorded_attributes = frozenset({"deviations"})

    @property
    def native_value(self):
        return len(self.coordinator.data.stop_deviations)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""

        if not self.coordinator.data:
            return {}

        return {"deviations": self.coordinator.data.stop_deviations}


class NextDepartureSensor(BaseDepartureSensor):

    entity_description = SensorEntityDescription(
        key="next_departure",
        icon="mdi:clock",
        has_entity_name=True,
        name="Next Departure",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    )

    @property
    def native_value(self):
        if (departure := self._next_departure()) is None:
            return None

        return departure.expected or departure.scheduled
