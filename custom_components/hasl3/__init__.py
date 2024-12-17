import logging

from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, ServiceCall

from custom_components.hasl3.haslworker import HaslWorker
from custom_components.hasl3.rrapi import rrapi_sl
from custom_components.hasl3.slapi import SLRoutePlanner31TripApi

from .const import (
    CONF_INTEGRATION_ID,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    SCHEMA_VERSION,
    SENSOR_ROUTE,
    SENSOR_VEHICLE_LOCATION,
)
from .services.sl_find_location import register as register_sl_find_location
from .services.sl_find_trip_id import register as register_sl_find_trip_id
from .services.sl_find_trip_pos import register as register_sl_find_trip_pos

logger = logging.getLogger(f"custom_components.{DOMAIN}.core")
serviceLogger = logging.getLogger(f"custom_components.{DOMAIN}.services")

EventOrService = Event | ServiceCall


async def async_setup(hass: HomeAssistant, config: ConfigEntry):
    """Set up HASL integration"""
    logger.debug("[setup] Entering")

    if DOMAIN not in hass.data:
        hass.data.setdefault(DOMAIN, {})

    try:
        if "worker" not in hass.data[DOMAIN]:
            logger.debug("[setup] No worker present")
            hass.data[DOMAIN] = {"worker": HaslWorker(hass)}
            logger.debug("[setup] Worker created")
    except:
        logger.error("[setup] Could not get worker")
        return False

    # SERVICE FUNCTIONS
    async def rr_find_location(service: EventOrService):
        serviceLogger.debug("[rr_find_location] Entered")
        search_string = service.data.get("search_string")
        api_key = service.data.get("api_key")

        serviceLogger.debug(
            f"[rr_find_location] Looking for '{search_string}' with key {api_key}"
        )

        try:
            rrapi = rrapi_sl(api_key)
            requestResult = await rrapi.request(search_string)
            serviceLogger.debug("[rr_find_location] Completed")
            hass.bus.fire(
                DOMAIN,
                {
                    "source": "rr_find_location",
                    "state": "success",
                    "result": requestResult,
                },
            )

        except Exception as e:
            serviceLogger.debug("[rr_find_location] Lookup failed")
            hass.bus.fire(
                DOMAIN,
                {
                    "source": "rr_find_location",
                    "state": "error",
                    "result": f"Exception occured during execution: {str(e)}",
                },
            )

    async def sl_find_trip_pos(service: EventOrService):
        serviceLogger.debug("[sl_find_trip_pos] Entered")
        olat = service.data.get("orig_lat")
        olon = service.data.get("orig_long")
        dlat = service.data.get("dest_lat")
        dlon = service.data.get("dest_long")
        api_key = service.data.get("api_key")

        serviceLogger.debug(
            f"[sl_find_trip_pos] Finding from '{olat} {olon}' to '{dlat} {dlon}' with key {api_key}"
        )

        try:
            rp3api = SLRoutePlanner31TripApi(api_key)
            requestResult = await rp3api.request("", "", olat, olon, dlat, dlon)
            serviceLogger.debug("[sl_find_trip_pos] Completed")
            hass.bus.fire(
                DOMAIN,
                {
                    "source": "sl_find_trip_pos",
                    "state": "success",
                    "result": requestResult,
                },
            )

        except Exception as e:
            serviceLogger.debug("[sl_find_trip_pos] Lookup failed")
            hass.bus.fire(
                DOMAIN,
                {
                    "source": "sl_find_trip_pos",
                    "state": "error",
                    "result": f"Exception occured during execution: {str(e)}",
                },
            )

    async def eventListener(service: Event):
        serviceLogger.debug("[eventListener] Entered")

        command = service.data.get("cmd")

        if command == "rr_find_location":
            hass.async_add_job(rr_find_location(service))
            serviceLogger.debug("[eventListener] Dispatched to rr_find_location")

        if command == "sl_find_trip_pos":
            hass.async_add_job(sl_find_trip_pos(service))
            serviceLogger.debug("[eventListener] Dispatched to sl_find_trip_pos")

    logger.debug("[setup] Registering services")
    try:
        register_sl_find_location(hass)
        register_sl_find_trip_id(hass)
        register_sl_find_trip_pos(hass)
        hass.services.async_register(DOMAIN, "rr_find_location", rr_find_location)
        logger.debug("[setup] Service registration completed")
    except:
        logger.error("[setup] Service registration failed")

    logger.debug("[setup] Registering event listeners")
    try:
        hass.bus.async_listen(DOMAIN, eventListener)
        logger.debug("[setup] Registering event listeners completed")
    except:
        logger.error("[setup] Registering event listeners failed")

    hass.data[DOMAIN]["worker"].status.startup_in_progress = False
    logger.debug("[setup] Completed")
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    logger.debug("[migrate_entry] Entered")

    logger.debug(
        "[migrate_entry] Migrating configuration from schema version %s to version %s",
        config_entry.version,
        SCHEMA_VERSION,
    )

    data = {**config_entry.data}
    options = {**config_entry.options}

    if (
        config_entry.version != "1"
        and config_entry.version != "2"
        and config_entry.version != "3"
    ):
        for option in config_entry.options:
            logger.debug(
                f"[migrate_entry] set {option} = {config_entry.options[option]}"
            )
            data[option] = config_entry.options[option]

    if config_entry.version == "2" and SCHEMA_VERSION == "3":
        # TODO: write migration
        # if data[CONF_INTEGRATION_TYPE] == "Departures":
        #     data[CONF_INTEGRATION_TYPE] = SENSOR_STANDARD
        #     logger.debug(
        #         f"[migrate_entry] migrate from Departures to {SENSOR_STANDARD}"
        #     )

        # TODO: write migration
        # if data[CONF_INTEGRATION_TYPE] == "Traffic Status":
        #     data[CONF_INTEGRATION_TYPE] = SENSOR_STATUS
        #     logger.debug(
        #         f"[migrate_entry] migrate from Traffic Status to {SENSOR_STATUS}"
        #     )
        if data[CONF_INTEGRATION_TYPE] == "Vehicle Locations":
            data[CONF_INTEGRATION_TYPE] = SENSOR_VEHICLE_LOCATION
            logger.debug(
                f"[migrate_entry] migrate from Vehicle Locations to {SENSOR_VEHICLE_LOCATION}"
            )

        # TODO: write migration
        # if data[CONF_INTEGRATION_TYPE] == "Deviations":
        #     data[CONF_INTEGRATION_TYPE] = "SL Deviations"
        #     logger.debug(
        #         f"[migrate_entry] migrate from Deviations to SL Deviations"
        #     )
        if data[CONF_INTEGRATION_TYPE] == "Route":
            data[CONF_INTEGRATION_TYPE] = SENSOR_ROUTE
            logger.debug(f"[migrate_entry] migrate from Route to {SENSOR_ROUTE}")

    if config_entry.version == 3 and SCHEMA_VERSION == "4":
        # split data into static and configurable part
        new_data = {
            k: v
            for k, v in data.items()
            if k in (CONF_INTEGRATION_ID, CONF_INTEGRATION_TYPE)
        }
        options = {k: v for k, v in data.items() if k not in new_data}
        data = new_data
        config_entry.version = 4

    try:
        hass.config_entries.async_update_entry(config_entry, data=data, options=options)
        logger.debug("[migrate_entry] Completed")
    except Exception as e:
        logger.error(f"[migrate_entry] Failed: {str(e)}")
        return False

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up HASL entry."""

    await hass.config_entries.async_forward_entry_setups(entry, [SENSOR_DOMAIN])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload HASL entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, [SENSOR_DOMAIN])

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
