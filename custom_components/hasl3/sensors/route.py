"""Departure sensor for hasl3."""

import logging
from asyncio import timeout
from datetime import timedelta
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryAuthFailed,
    ConfigEntryError,
)
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector as sel
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from tsl.models.stops import LookupSiteId

from .. import const
from ..slapi import SLAPI_Error, SLRoutePlanner31TripApi
from .device import SL_TRAFFIK_DEVICE_INFO

logger = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(const.CONF_SOURCE): sel.NumberSelector(
            sel.NumberSelectorConfig(min=0, mode=sel.NumberSelectorMode.BOX)
        ),
        vol.Required(const.CONF_DESTINATION): sel.NumberSelector(
            sel.NumberSelectorConfig(min=0, mode=sel.NumberSelectorMode.BOX)
        ),
        vol.Optional(const.CONF_SENSOR): sel.EntitySelector(
            sel.EntitySelectorConfig(domain="binary_sensor")
        ),
        vol.Required(const.CONF_SCAN_INTERVAL, default=300): sel.NumberSelector(
            sel.NumberSelectorConfig(
                min=0,
                unit_of_measurement="seconds",
                mode=sel.NumberSelectorMode.BOX,
            )
        ),
    }
)


async def async_setup_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
):
    coordinator = RouteDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    return coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the sensor platform."""

    async_add_entities([RouteTripsSensor(entry)])


class RouteDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching Route data API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        self._api_key = config_entry.data[const.CONF_RP3_KEY]
        self._from = LookupSiteId.from_siteid(
            int(config_entry.options[const.CONF_SOURCE])
        )
        self._to = LookupSiteId.from_siteid(
            int(config_entry.options[const.CONF_DESTINATION])
        )
        self._sensor_id: str | None = config_entry.options.get(const.CONF_SENSOR)
        interval = timedelta(seconds=config_entry.options[const.CONF_SCAN_INTERVAL])

        if TYPE_CHECKING:
            assert config_entry.unique_id

        device_info = SL_TRAFFIK_DEVICE_INFO.copy()
        device_info["identifiers"] = {(const.DOMAIN, config_entry.entry_id)}
        device_info["name"] = config_entry.title
        self.device_info = device_info

        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            config_entry=config_entry,
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

        client = SLRoutePlanner31TripApi(
            self._api_key,
            async_get_clientsession(self.hass),
        )
        async with timeout(10):
            try:
                data = await client.request((self._from, self._to))
                data = client.transform(data)
            except SLAPI_Error as error:
                if error.code == 1002:
                    raise ConfigEntryAuthFailed(error) from error
                raise ConfigEntryError(error) from error

            return data


class RouteTripsSensor(
    CoordinatorEntity[RouteDataUpdateCoordinator],
    SensorEntity,
):
    _attr_attribution = "Stockholm Lokaltrafik"
    _unrecorded_attributes = frozenset({"route"})

    entity_description = SensorEntityDescription(
        key="route",
        icon="mdi:train",
        has_entity_name=True,
        name="Trips",
    )

    def __init__(
        self,
        entry: ConfigEntry[RouteDataUpdateCoordinator],
    ):
        super().__init__(entry.runtime_data)

        self._attr_unique_id = f"{entry.entry_id}_{self.entity_description.key}"
        self._attr_device_info = self.coordinator.device_info

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None

        return len(self.coordinator.data["trips"])

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}

        return {"route": self.coordinator.data}
