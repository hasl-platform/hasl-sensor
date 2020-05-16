"""SL Platform"""
import logging
from homeassistant import config_entries
from homeassistant.helpers import discovery
from homeassistant.const import __version__ as HAVERSION
from homeassistant.const import EVENT_HOMEASSISTANT_START
from custom_components.hasl.haslworker.configuration import Configuration
from homeassistant.exceptions import ConfigEntryNotReady, ServiceNotFound
from homeassistant.helpers.event import async_call_later

from .globals import get_worker

from .const import (
    DOMAIN,
    DOMAIN_DATA,
    VERSION,
    STARTUP_MESSAGE
)

async def async_setup(hass, config):
    """Set up this integration using yaml."""
    worker = get_worker()
    if DOMAIN not in config:
        return True
    if worker.configuration and worker.configuration.config_type == "flow":
        return True
    hass.data[DOMAIN] = config
    worker.hass = hass
    worker.configuration = Configuration.from_dict(
        config[DOMAIN], config[DOMAIN].get("options")
    )
    worker.configuration.config = config
    worker.configuration.config_type = "yaml"
    await startup_wrapper_for_yaml()
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
        )
    )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up this integration using UI."""
    worker = get_worker()
    conf = hass.data.get(DOMAIN)
    if config_entry.source == config_entries.SOURCE_IMPORT:
        if conf is None:
            hass.async_create_task(
                hass.config_entries.async_remove(config_entry.entry_id)
            )
        return False
    worker.hass = hass
    worker.configuration = Configuration.from_dict(
        config_entry.data, config_entry.options
    )
    worker.configuration.config_type = "flow"
    worker.configuration.config_entry = config_entry
    config_entry.add_update_listener(reload_hasl)
    #try:
    startup_result = await hasl_startup()       
    #except Exception:
    #    startup_result = False
    #if not startup_result:
    #    worker.system.disabled = True
    #    raise ConfigEntryNotReady
    #worker.system.disabled = False
    return startup_result

async def startup_wrapper_for_yaml():
    """Startup wrapper for yaml config."""
    worker = get_worker()
    try:
        startup_result = await hasl_startup()
    except Exception:
        startup_result = False
    if not startup_result:
        worker.system.disabled = True
        async_call_later(worker.hass, 900, startup_wrapper_for_yaml())
        return
    worker.system.disabled = False
    
def add_services():
    """Add sensor."""
    worker = get_worker()

    #hass.services.register(DOMAIN, 'clear_cache', clear_cache)
    #hass.services.register(DOMAIN, 'dump_cache', dump_cache)
    
    
def add_sensor():
    """Add sensor."""
    worker = get_worker()

    try:
        if worker.configuration.config_type == "yaml":
            worker.hass.async_create_task(
                discovery.async_load_platform(
                    worker.hass, "sensor", DOMAIN, {}, worker.configuration.config
                )
            )
        else:
            worker.hass.async_add_job(
                worker.hass.config_entries.async_forward_entry_setup(
                    worker.configuration.config_entry, "sensor"
                )
            )
    except ValueError:
        pass    

async def hasl_startup():
    """HASL startup tasks."""
    worker = get_worker()
    
    #TODO NOT WORKING!!!!!!
    #if worker.configuration.debug:
    #    try:
    #        await worker.hass.services.async_call(
    #            "logger", "set_level", {"hasl": "debug"}
    #        )
    #        await worker.hass.services.async_call(
    #            "logger", "set_level", {"queueman": "debug"}
    #        )
    #    except ServiceNotFound:
    #        worker.logger.error(
    #            "Could not set logging level to debug, logger is not enabled"
    #        )

    worker.logger.debug(f"Configuration type: {worker.configuration.config_type}")
    worker.version = VERSION
    worker.logger.info(STARTUP_MESSAGE)
    worker.system.config_path = worker.hass.config.path()
    worker.system.ha_version = HAVERSION
    worker.system.disabled = False

    # Setup startup tasks
    if worker.configuration.config_type == "yaml":
        worker.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, worker.startup_tasks())
    else:
        async_call_later(worker.hass, 5, worker.startup_tasks())


    await worker.hass.async_add_executor_job(add_sensor)
    await worker.hass.async_add_executor_job(add_services)

    return True

async def async_remove_entry(hass, config_entry):
    """Handle removal of an entry."""
    worker = get_worker()
    worker.logger.info("Disabling HASL")
    
    worker.logger.info("Removing recuring tasks")
    for task in worker.recuring_tasks:
        task()
        
    worker.logger.info("Removing sensor")
    try:
        await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    except ValueError:
        return
        
    worker.system.disabled = True
    worker.logger.info("HASL is now disabled")


async def reload_hasl(hass, config_entry):
    """Reload HASL."""
    await async_remove_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
