"""Config flow for the HASL component."""

from collections.abc import Mapping
import logging
from typing import Any, cast
import uuid

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow as ConfigFlowBase
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

from .config_schema import START_CONFIG_SCHEMA, schema_by_type
from .const import (
    CONF_DIRECTION,
    CONF_INTEGRATION_ID,
    CONF_INTEGRATION_TYPE,
    CONF_LINE,
    CONF_SCAN_INTERVAL,
    CONF_SITE_ID,
    CONF_TIMEWINDOW,
    DOMAIN,
    SCHEMA_VERSION,
    SENSOR_STATUS,
)

logger = logging.getLogger(f"custom_components.{DOMAIN}.config")


async def get_schema_by_handler(handler: SchemaCommonFlowHandler):
    """Return the schema for the handler."""
    return schema_by_type(handler.options[CONF_INTEGRATION_TYPE])


async def validate_integration(handler: SchemaCommonFlowHandler, data: dict[str, Any]):
    if data[CONF_INTEGRATION_TYPE] == SENSOR_STATUS:
        # check if there any other configured status sensors
        entries = handler.parent_handler.hass.config_entries.async_entries(DOMAIN)
        for entry in entries:
            if entry.data[CONF_INTEGRATION_TYPE] == SENSOR_STATUS:
                raise SchemaFlowError("only_one_status_sensor")

    return data


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=START_CONFIG_SCHEMA,
        validate_user_input=validate_integration,
        next_step="config",
    ),
    "config": SchemaFlowFormStep(get_schema_by_handler),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step="user"),  # redirect to 'user' step
    "user": SchemaFlowFormStep(get_schema_by_handler),
}


class ConfigFlow(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for HASL."""

    VERSION = SCHEMA_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])

    @callback
    def async_config_flow_finished(self, options: Mapping[str, Any]) -> None:
        """Mutate options after all steps are done."""

        int_fields = (
            CONF_SITE_ID,
            CONF_SCAN_INTERVAL,
            CONF_TIMEWINDOW,
            CONF_LINE,
            CONF_DIRECTION,
        )
        for field in int_fields:
            if (value := options.get(field)) is not None:
                options[field] = int(value)

    @callback
    def async_create_entry(
        self,
        data: Mapping[str, Any],
        **kwargs: Any,
    ) -> FlowResult:
        """Finish config flow and create a config entry."""

        self.async_config_flow_finished(data)

        # split configuration in two parts
        return ConfigFlowBase.async_create_entry(
            self,
            data={
                CONF_INTEGRATION_ID: uuid.uuid1(),  # TODO: remove!
                CONF_INTEGRATION_TYPE: data[CONF_INTEGRATION_TYPE],
            },
            options=data,
            title=self.async_config_entry_title(data),
        )
