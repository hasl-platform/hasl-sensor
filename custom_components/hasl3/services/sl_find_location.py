import logging
from functools import partial

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from tsl.clients.stoplookup import StopLookupClient

from ..const import DOMAIN

logger = logging.getLogger(__name__)


API_KEY = "api_key"
SEARCH_STRING = "search_string"


SCHEMA = vol.Schema(
    {
        vol.Required(API_KEY): str,
        vol.Required(SEARCH_STRING): str,
    }
)


async def service(hass: HomeAssistant, call: ServiceCall):
    search_string = call.data.get(SEARCH_STRING)
    api_key = call.data.get(API_KEY)

    logger.debug(f"Searching for '{search_string}' with key {'*' * len(api_key)}")

    session = async_get_clientsession(hass)
    client = StopLookupClient(api_key, session)

    requestResult = await client.get_stops(search_string)
    logger.debug(
        f"Completed search for '{search_string}'. Found {len(requestResult)} results"
    )

    return {
        SEARCH_STRING: search_string,
        "results": [
            {
                "name": r.Name,
                "site_id": r.SiteId.transport_siteid,
            }
            for r in requestResult
        ],
    }


def register(hass: HomeAssistant):
    hass.services.async_register(
        DOMAIN,
        "sl_find_location",
        partial(service, hass),
        schema=SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
