"""Config flow for the HASL component."""

import logging
import uuid
from typing import Any, cast
from functools import partial

import voluptuous as vol
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigEntry, ConfigFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector as sel
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from tsl.clients.stoplookup import StopLookupClient

from .config_schema import NAME_CONFIG_SCHEMA, schema_by_type
from .const import (
    CONF_INTEGRATION_LIST,
    CONF_INTEGRATION_ID,
    CONF_INTEGRATION_TYPE,
    CONF_SITE_ID,
    DOMAIN,
    SCHEMA_VERSION,
    SENSOR_DEPARTURE,
    SENSOR_STATUS,
)

logger = logging.getLogger(__name__)


async def get_schema_by_handler(handler: SchemaCommonFlowHandler):
    """Return the schema for the handler."""
    parent_handler = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    return schema_by_type(parent_handler.config_entry.data[CONF_INTEGRATION_TYPE])


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step="user"),  # redirect to 'user' step
    "user": SchemaFlowFormStep(get_schema_by_handler),
}


LOOKUP_API_KEY = "lookup_api_key"
LOOKUP_SEARCH_KEY = "lookup_search_key"


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HASL."""

    VERSION = SCHEMA_VERSION
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self):
        self._options = {}

        # plug in the handlers for the legacy integration types
        for step in (
            x
            for x in CONF_INTEGRATION_LIST
            if x not in {SENSOR_DEPARTURE, SENSOR_STATUS}
        ):
            setattr(self, f"async_step_{step}", partial(self.async_step_legacy, step))

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):

        # TODO: add back legacy sensor types
        return self.async_show_menu(
            step_id="user", menu_options=[SENSOR_DEPARTURE, SENSOR_STATUS]
        )

    async def async_step_departure_v2(self, user_input: dict[str, Any] | None = None):
        self._options[CONF_INTEGRATION_TYPE] = SENSOR_DEPARTURE

        return self.async_show_menu(
            step_id="departure_v2", menu_options=["lookup_location", "name"]
        )

    async def async_step_status_v2(self, user_input: dict[str, Any] | None = None):
        self._options[CONF_INTEGRATION_TYPE] = SENSOR_STATUS

        # TODO: evaluate, if we need to check for existing status sensors
        # check if there any other configured status sensors
        # entries = self.hass.config_entries.async_entries(DOMAIN)
        # for entry in entries:
        #     if entry.data[CONF_INTEGRATION_TYPE] == SENSOR_STATUS:
        #         raise SchemaFlowError("only_one_status_sensor")

        return await self.async_step_name()

    async def async_step_lookup_location(
        self, user_input: dict[str, Any] | None = None
    ):
        if (
            user_input is None
            or (
                api_key := self._options.get(
                    LOOKUP_API_KEY, user_input.get(LOOKUP_API_KEY)
                )
            )
            is None
        ):
            old_errors = user_input and user_input.get("errors")
            return self.async_show_form(
                step_id="lookup_location",
                data_schema=vol.Schema(
                    {
                        vol.Required(LOOKUP_API_KEY): str,
                    },
                ),
                errors=old_errors,
            )
        else:
            self._options[LOOKUP_API_KEY] = api_key

        if (search_key := user_input.get(LOOKUP_SEARCH_KEY)) is None:
            return self.async_show_form(
                step_id="lookup_location",
                data_schema=vol.Schema(
                    {
                        vol.Required(LOOKUP_SEARCH_KEY): str,
                    }
                ),
            )

        # if the search key has changed, reset the site id
        if last_search_key := self._options.get(LOOKUP_SEARCH_KEY):
            if last_search_key != search_key:
                self._options.pop(LOOKUP_SEARCH_KEY, None)
                user_input.pop(CONF_SITE_ID, None)
        else:
            self._options[LOOKUP_SEARCH_KEY] = search_key

        # the result was chosen
        if site_id := user_input.get(CONF_SITE_ID):
            user_input.pop(LOOKUP_SEARCH_KEY, None)
            self._options.pop(LOOKUP_API_KEY, None)
            self._options.pop(LOOKUP_SEARCH_KEY, None)
            self._options[CONF_SITE_ID] = int(site_id)
            return await self.async_step_name()

        # perform the search
        session = async_get_clientsession(self.hass)
        client = StopLookupClient(api_key, session)

        try:
            stops = await client.get_stops(search_key)
        except Exception:  # TOOD: catch specific exceptions
            self._options.pop(LOOKUP_API_KEY, None)
            return await self.async_step_lookup_location(
                {"errors": {"base": "lookup_failed"}}
            )

        stop_options: list[sel.SelectOptionDict] = [
            {"value": str(stop.SiteId.transport_siteid), "label": stop.Name}
            for stop in stops
        ]
        if first_option := next(iter(stop_options), None):
            first_option = first_option["value"]

        return self.async_show_form(
            step_id="lookup_location",
            data_schema=vol.Schema(
                {
                    vol.Required(LOOKUP_SEARCH_KEY, default=search_key): str,
                    vol.Optional(
                        CONF_SITE_ID,  # default=first_option or vol.UNDEFINED
                        description={"suggested_value": first_option},
                    ): sel.SelectSelector(
                        sel.SelectSelectorConfig(
                            options=stop_options,
                            translation_key=CONF_SITE_ID,
                        )
                    ),
                }
            ),
        )

    async def async_step_legacy(
        self, type_: str, user_input: dict[str, Any] | None = None
    ):
        self._options[CONF_INTEGRATION_TYPE] = type_
        return await self.async_step_name()

    async def async_step_name(self, user_input: dict[str, Any] | None = None):
        if not user_input:
            return self.async_show_form(step_id="name", data_schema=NAME_CONFIG_SCHEMA)

        self._options[CONF_NAME] = user_input[CONF_NAME]
        return await self.async_step_config()

    async def async_step_config(self, user_input: dict[str, Any] | None = None):
        type_ = self._options[CONF_INTEGRATION_TYPE]

        schema = schema_by_type(type_)

        # patch schema with suggested values from self._options for known types
        if type_ == SENSOR_DEPARTURE:
            if site_id := self._options.get(CONF_SITE_ID):
                schema = self.add_suggested_values_to_schema(
                    schema,
                    {CONF_SITE_ID: site_id},
                )

        if user_input is None:
            return self.async_show_form(step_id="config", data_schema=schema)

        data = {
            CONF_INTEGRATION_TYPE: type_,
        }

        # TODO: remove legacy: generate a new integration id
        if type_ not in (SENSOR_DEPARTURE, SENSOR_STATUS):
            data[CONF_INTEGRATION_ID] = uuid.uuid1()

        return self.async_create_entry(
            title=self._options[CONF_NAME], data=data, options=user_input
        )
