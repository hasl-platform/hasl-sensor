import logging
from functools import partial

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import DOMAIN
from ..slapi import SLRoutePlanner31TripApi

logger = logging.getLogger(__name__)


API_KEY = "api_key"
ORIGIN_LAT = "orig_lat"
ORIGIN_LONG = "orig_long"
DESTINATION_LAT = "dest_lat"
DESTINATION_LONG = "dest_long"


SCHEMA = vol.Schema(
    {
        vol.Required(API_KEY): str,
        vol.Required(ORIGIN_LAT): str,
        vol.Required(ORIGIN_LONG): str,
        vol.Required(DESTINATION_LAT): str,
        vol.Required(DESTINATION_LONG): str,
    }
)


async def service(hass: HomeAssistant, call: ServiceCall):
    api_key = call.data.get(API_KEY)
    orig_lat, orig_lon = call.data.get(ORIGIN_LAT), call.data.get(ORIGIN_LONG)
    dest_lat, dest_lon = (
        call.data.get(DESTINATION_LAT),
        call.data.get(DESTINATION_LONG),
    )

    logger.debug(
        f"Searching for trip [{orig_lat}, {orig_lon}] -> [{dest_lat}, {dest_lon}] with key {'*' * len(api_key)}"
    )

    session = async_get_clientsession(hass)
    client = SLRoutePlanner31TripApi(api_key, session)
    requestResult = await client.request((orig_lat, orig_lon, dest_lat, dest_lon))
    return requestResult


def register(hass: HomeAssistant):
    hass.services.async_register(
        DOMAIN,
        "sl_find_trip_pos",
        partial(service, hass),
        schema=SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
