import logging
from functools import partial

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import DOMAIN
from ..slapi import SLRoutePlanner31TripApi

logger = logging.getLogger(__name__)


API_KEY = "api_key"
ORIGIN = "org"
DESTINATION = "dest"


SCHEMA = vol.Schema(
    {
        vol.Required(API_KEY): str,
        vol.Required(ORIGIN): int,
        vol.Required(DESTINATION): int,
    }
)


async def service(hass: HomeAssistant, call: ServiceCall):
    api_key = call.data.get(API_KEY)
    origin = f"30010{call.data.get(ORIGIN)}"
    destination = f"30010{call.data.get(DESTINATION)}"

    logger.debug(
        f"Searching for trip {origin} -> {destination} with key {'*' * len(api_key)}"
    )

    session = async_get_clientsession(hass)
    client = SLRoutePlanner31TripApi(api_key, session)
    requestResult = await client.request((origin, destination))
    return requestResult


def register(hass: HomeAssistant):
    hass.services.async_register(
        DOMAIN,
        "sl_find_trip_id",
        partial(service, hass),
        schema=SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
