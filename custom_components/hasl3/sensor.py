""" SL Platform Sensor """
import logging
import math
import datetime
import jsonpickle
import time

from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.core import HomeAssistant, State
from homeassistant.util.dt import now

from .const import (
    DOMAIN,
    HASL_VERSION,
    DEVICE_NAME,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEVICE_GUID,
    DEVICE_TYPE,
    SENSOR_STANDARD,
    SENSOR_STATUS,
    SENSOR_VEHICLE_LOCATION,
    SENSOR_DEVIATION,
    SENSOR_ROUTE,
    CONF_ANALOG_SENSORS,
    CONF_FP_PT,
    CONF_FP_RB,
    CONF_FP_TVB,
    CONF_FP_SB,
    CONF_FP_LB,
    CONF_FP_SPVC,
    CONF_FP_TB1,
    CONF_FP_TB2,
    CONF_TL2_KEY,
    CONF_RI4_KEY,
    CONF_SI2_KEY,
    CONF_RP3_KEY,
    CONF_SITE_ID,
    CONF_SENSOR,
    CONF_LINES,
    CONF_INTEGRATION_TYPE,
    CONF_INTEGRATION_ID,
    CONF_DEVIATION_LINES,
    CONF_DEVIATION_STOPS,
    CONF_DEVIATION_LINE,
    CONF_DEVIATION_STOP,
    CONF_SENSOR_PROPERTY,
    CONF_DIRECTION,
    CONF_TIMEWINDOW,
    CONF_SCAN_INTERVAL,
    CONF_SOURCE,
    CONF_DESTINATION,
    STATE_ON,
    CONF_TRANSPORT_MODE_LIST
)

logger = logging.getLogger(f"custom_components.{DOMAIN}.sensors")

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities(await setup_hasl_sensor(hass,config))

async def async_setup_entry(hass, config_entry, async_add_devices):
    async_add_devices(await setup_hasl_sensor(hass, config_entry))

async def setup_hasl_sensor(hass,config):
    """Setup sensor platform."""
    logger.debug("[setup_hasl_sensor] Entered")

    sensors = []
    worker = hass.data[DOMAIN]["worker"]
   
    try:
        logger.debug("[setup_hasl_sensor] Setting up RI4 sensors..")
        if config.data[CONF_INTEGRATION_TYPE]==SENSOR_STANDARD:
            if CONF_RI4_KEY in config.options and CONF_SITE_ID in config.options:
                await worker.assert_ri4(config.options[CONF_RI4_KEY],config.options[CONF_SITE_ID])
                sensors.append(HASLDepartureSensor(hass,config,config.options[CONF_SITE_ID]))
            logger.debug("[setup_hasl_sensor] Force proccessing RI4 sensors")
            await worker.process_ri4();
        logger.debug("[setup_hasl_sensor] Completed setting up RI4 sensors")
    except Exception as e:
        logger.error(f"[setup_hasl_sensor] Failed to setup RI4 sensors {str(e)}")


    try:
        logger.debug("[setup_hasl_sensor] Setting up SI2 sensors..")
        if config.data[CONF_INTEGRATION_TYPE]==SENSOR_DEVIATION:
            if CONF_SI2_KEY in config.options:
                for deviationid in ','.join(set(config.options[CONF_DEVIATION_LINES].split(','))).split(','):
                    await worker.assert_si2_line(config.options[CONF_SI2_KEY],deviationid)
                    sensors.append(HASLDeviationSensor(hass,config,CONF_DEVIATION_LINE,deviationid))
                for deviationid in ','.join(set(config.options[CONF_DEVIATION_STOPS].split(','))).split(','):
                    await worker.assert_si2_stop(config.options[CONF_SI2_KEY],deviationid)
                    sensors.append(HASLDeviationSensor(hass,config,CONF_DEVIATION_STOP,deviationid))
            logger.debug("[setup_hasl_sensor] Force proccessing SI2 sensors")
            await worker.process_si2()
        logger.debug("[setup_hasl_sensor] Completed setting up SI2 sensors")
    except Exception as e:
        logger.error(f"[setup_hasl_sensor] Failed to setup SI2 sensors {str(e)}")


    try:
        logger.debug("[setup_hasl_sensor] Setting up RP3 sensors..")
        if config.data[CONF_INTEGRATION_TYPE]==SENSOR_ROUTE:
            if CONF_RP3_KEY in config.options:            
                await worker.assert_rp3(config.options[CONF_RP3_KEY],config.options[CONF_SOURCE],config.options[CONF_DESTINATION])
                sensors.append(HASLRouteSensor(hass,config,f"{config.options[CONF_SOURCE]}-{config.options[CONF_DESTINATION]}"))
            logger.debug("[setup_hasl_sensor] Force proccessing RP3 sensors")
            await worker.process_rp3()
        logger.debug("[setup_hasl_sensor] Completed setting up RP3 sensors")
    except Exception as e:
        logger.error(f"[setup_hasl_sensor] Failed to setup RP3 sensors {str(e)}")
            

    try:
        logger.debug("[setup_hasl_sensor] Setting up TL2 sensors..")
        if config.data[CONF_INTEGRATION_TYPE]==SENSOR_STATUS:
            if config.options[CONF_ANALOG_SENSORS]:
                if CONF_TL2_KEY in config.options:
                    await worker.assert_tl2(config.options[CONF_TL2_KEY])

                    for sensortype in CONF_TRANSPORT_MODE_LIST:
                        if sensortype in config.options and config.options[sensortype]:
                            sensors.append(HASLTrafficStatusSensor(hass,config,sensortype))
                    
                logger.debug("[setup_hasl_sensor] Force proccessing TL2 sensors")
                await worker.process_tl2()
        logger.debug("[setup_hasl_sensor] Completed setting up TL2 sensors")
    except Exception as e:
        logger.error(f"[setup_hasl_sensor] Failed to setup Tl2 sensors {str(e)}")
            

    try:
        logger.debug("[setup_hasl_sensor] Setting up FP sensors..")
        if config.data[CONF_INTEGRATION_TYPE]==SENSOR_VEHICLE_LOCATION:
            if CONF_FP_PT in config.options and config.options[CONF_FP_PT]:
                await worker.assert_fp("PT")
                sensors.append(HASLVehicleLocationSensor(hass,config,'PT'))
            if CONF_FP_RB in config.options and config.options[CONF_FP_RB]:
                await worker.assert_fp("RB")
                sensors.append(HASLVehicleLocationSensor(hass,config,'RB'))
            if CONF_FP_TVB in config.options and config.options[CONF_FP_TVB]:
                await worker.assert_fp("TVB")
                sensors.append(HASLVehicleLocationSensor(hass,config,'TVB'))
            if CONF_FP_SB in config.options and config.options[CONF_FP_SB]:
                await worker.assert_fp("SB")
                sensors.append(HASLVehicleLocationSensor(hass,config,'SB'))
            if CONF_FP_LB in config.options and config.options[CONF_FP_LB]:
                await worker.assert_fp("LB")
                sensors.append(HASLVehicleLocationSensor(hass,config,'LB'))
            if CONF_FP_SPVC in config.options and config.options[CONF_FP_SPVC]:
                await worker.assert_fp("SpvC")
                sensors.append(HASLVehicleLocationSensor(hass,config,'SpvC'))
            if CONF_FP_TB1 in config.options and config.options[CONF_FP_TB1]:
                await worker.assert_fp("TB1")
                sensors.append(HASLVehicleLocationSensor(hass,config,'TB1'))
            if CONF_FP_TB2 in config.options and config.options[CONF_FP_TB2]:
                await worker.assert_fp("TB2")
                sensors.append(HASLVehicleLocationSensor(hass,config,'TB2'))
            if CONF_FP_TB2 in config.options and config.options[CONF_FP_TB2]:
                await worker.assert_fp("TB3")
                sensors.append(HASLVehicleLocationSensor(hass,config,'TB3'))
            logger.debug("[setup_hasl_sensor] Force proccessing FP sensors")
            await worker.process_fp()
        logger.debug("[setup_hasl_sensor] Completed setting up FP sensors")
    except Exception as e:
        logger.error(f"[setup_hasl_sensor] Failed to setup FP sensors {str(e)}")


    logger.debug("[setup_hasl_sensor] Completed")
    return sensors
    
class HASLDevice(Entity):
    """HASL Device class."""
    @property
    def device_info(self):
        """Return device information about HASL Device."""
        return {
            "identifiers": {(DOMAIN, DEVICE_GUID)},
            "name": DEVICE_NAME,
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
            "sw_version": HASL_VERSION,
            "entry_type": DEVICE_TYPE
        }
        
class HASLRouteSensor(HASLDevice):
    """HASL Train Location Sensor class."""

    def __init__(self, hass, config, trip):
        """Initialize."""
        self._hass = hass
        self._config = config
        self._enabled_sensor = config.options[CONF_SENSOR]
        self._trip = trip
        self._name = f"SL {self._trip} Route Sensor ({self._config.title})"
        self._sensordata = []
        self._scan_interval = self._config.options[CONF_SCAN_INTERVAL] or 300
        self._worker = hass.data[DOMAIN]["worker"]

    async def async_update(self):
        """Update the sensor."""       

        logger.debug("[async_update] Entered")
        logger.debug(f"[async_update] Processing {self._name}")

        if self._worker.data.rp3[self._trip]["api_lastrun"]:
            if self._worker.checksensorstate(self._enabled_sensor,STATE_ON):
                if self._worker.getminutesdiff(now().strftime('%Y-%m-%d %H:%M:%S'), self._worker.data.rp3[self._trip]["api_lastrun"]) > self._config.options[CONF_SCAN_INTERVAL]:
                    try:
                        await self._worker.process_rp3()
                        logger.debug("[async_update] Update processed")
                    except Exception as e:
                        logger.debug("[async_update] Error occured during update")
                else:
                    logger.debug("[async_update] Not due for update, skipping")
                        

        self._sensordata = self._worker.data.rp3[self._trip]
        logger.debug("[async_update] Completed")        
        return

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"sl-route-{self._trip}-sensor-{self._config.data[CONF_INTEGRATION_ID]}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensordata == []:
            return 'Unknown'
        else:
            return len(self._sensordata["trips"])

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:train"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ""

    @property
    def scan_interval(self):
        """Return the unique id."""
        return self._scan_interval

    @property
    def device_state_attributes(self):
        
        val = {}
        
        if self._sensordata == []:
            return val
                      
        if self._sensordata["api_result"] == "Success":
            val['api_result'] = "Success"
        else:
            val['api_result'] = self._sensordata["api_error"]

        # Set values of the sensor.
        val['scan_interval'] = self._scan_interval
        val['refresh_enabled'] = self._worker.checksensorstate(self._enabled_sensor,STATE_ON)
        try:
            val['attribution'] = self._sensordata["attribution"]
            val['trips'] = self._sensordata["trips"]
            val['transfers'] = self._sensordata["transfers"]
            val['price'] = self._sensordata["price"]
            val['time'] = self._sensordata["time"]
            val['duration'] = self._sensordata["duration"]
            val['first_leg'] = self._sensordata["first_leg"]
            val['last_refresh'] = self._sensordata["last_updated"]
            val['trip_count'] = len(self._sensordata["trips"])
        except Exception as e:
            val['error'] = "NoDataYet"
            logger.debug(f"Data was not avaliable for processing when getting attributes for sensor {self._name}")
        
        return val                  
        
        
class HASLDepartureSensor(HASLDevice):
    """HASL Departure Sensor class."""

    def __init__(self, hass, config, siteid):
        """Initialize."""
        
        unit_table = {
            'min': 'min',
            'time': '',
            'deviations': '',
            'updated': '',
        }
    
        self._hass = hass
        self._config = config
        self._lines = config.options[CONF_LINES]
        self._siteid = str(siteid)
        self._name = f"SL Departure Sensor {self._siteid} ({self._config.title})"
        self._enabled_sensor = config.options[CONF_SENSOR]
        self._sensorproperty = config.options[CONF_SENSOR_PROPERTY]
        self._direction = config.options[CONF_DIRECTION]
        self._timewindow = config.options[CONF_TIMEWINDOW]
        self._nextdeparture_minutes = '0'
        self._nextdeparture_expected = '-'
        self._lastupdate = '-'
        self._unit_of_measure = unit_table.get(self._config.options[CONF_SENSOR_PROPERTY], 'min')
        self._sensordata = None
        self._scan_interval = self._config.options[CONF_SCAN_INTERVAL] or 300
        self._worker = hass.data[DOMAIN]["worker"]
        
    async def async_update(self):
        """Update the sensor."""

        logger.debug("[async_update] Entered")
        logger.debug(f"[async_update] Processing {self._name}")
        if self._worker.data.ri4[self._siteid]["api_lastrun"]:
            if self._worker.checksensorstate(self._enabled_sensor,STATE_ON):
                if self._worker.getminutesdiff(now().strftime('%Y-%m-%d %H:%M:%S'), self._worker.data.ri4[self._siteid]["api_lastrun"]) > self._config.options[CONF_SCAN_INTERVAL]:
                    try:
                        await self._worker.process_ri4()
                        logger.debug("[async_update] Update processed")
                    except Exception as e:
                        logger.debug("[async_update] Error occured during update")
                else:
                    logger.debug("[async_update] Not due for update, skipping")


        self._sensordata = self._worker.data.ri4[self._siteid]
        
        logger.debug("[async_update] Performing calculations")
        if f"stop_{self._siteid}" in self._worker.data.si2:
            if "data" in self._worker.data.si2[f"stop_{self._siteid}"]:
                self._sensordata["deviations"] = self._worker.data.si2[f"stop_{self._siteid}"]["data"]
            else: 
                self._sensordata["deviations"] = []
        else:
            self._sensordata["deviations"] = []

        if "last_updated" in self._sensordata:
            self._last_updated = self._sensordata["last_updated"]
        else:
            self._last_updated = now().strftime('%Y-%m-%d %H:%M:%S')    

        logger.debug("[async_update] Completed")                
        return

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"sl-stop-{self._siteid}-sensor-{self._config.data[CONF_INTEGRATION_ID]}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        sensorproperty = self._config.options[CONF_SENSOR_PROPERTY]

        if self._sensordata == []:
            return 'Unknown'
            
        if sensorproperty == 'min':
            next_departure = self.nextDeparture()
            if not next_departure:
                return '-'

            delta = next_departure['expected'] - datetime.datetime.now()
            expected_minutes = math.floor(delta.total_seconds() / 60)
            return expected_minutes

        # If the sensor should return the time at which next departure occurs.
        if sensorproperty == 'time':
            next_departure = self.nextDeparture()
            if not next_departure:
                return '-'

            expected = next_departure['expected'].strftime('%H:%M:%S')
            return expected

        # If the sensor should return the number of deviations.
        if sensorproperty == 'deviations':
            return len(self._sensordata["deviations"])

        if sensorproperty == 'updated':
            return self._sensordata["last_updated"]
            
        # Failsafe
        return '-'
        
    def nextDeparture(self):
        if not self._sensordata:
            return None

        now = datetime.datetime.now()
        if "data" in self._sensordata:
            for departure in self._sensordata["data"]:
                if departure['expected'] > now:
                    return departure
        return None        

    def filter_direction(self, departure):
        if self._direction == 0:
            return True
        return departure["direction"] == self._direction

    def filter_lines(self, departure):
        if self._lines == []:
            return True
        return departure["line"] in self._lines

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:train"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measure

    @property
    def scan_interval(self):
        """Return the unique id."""
        return self._scan_interval

    @property
    def device_state_attributes(self):
        """ Return the sensor attributes ."""

        # Initialize the state attributes.
        
        val = {}

        if self._sensordata == [] or self._sensordata is None:
            return val

        # Format the next exptected time.
        next_departure = self.nextDeparture()
        if next_departure:
            expected_time = next_departure['expected']
            delta = expected_time - datetime.datetime.now()
            expected_minutes = math.floor(delta.total_seconds() / 60)
            expected_time = expected_time.strftime('%H:%M:%S')
        else:
            expected_time = '-'
            expected_minutes = '-'

        # Setup the unit of measure.
        if self._unit_of_measure != '':
            val['unit_of_measurement'] = self._unit_of_measure

        if self._sensordata["api_result"] == "Success":
            val['api_result'] = "Ok"
        else:
            val['api_result'] = self._sensordata["api_error"]
            
        # Set values of the sensor.
        val['scan_interval'] = self._scan_interval
        val['refresh_enabled'] = self._worker.checksensorstate(self._enabled_sensor,STATE_ON)

        try:
            departures = self._sensordata["data"]
            dirs_filtered = list(filter(self.filter_direction, departures))
            lines_filtered = list(filter(self.filter_lines, dirs_filtered))

            val['attribution'] = self._sensordata["attribution"]
            val['departures'] = lines_filtered
            val['deviations'] = self._sensordata["deviations"]
            val['last_refresh'] = self._sensordata["last_updated"]
            val['next_departure_minutes'] = expected_minutes
            val['next_departure_time'] = expected_time
            val['deviation_count'] = len(self._sensordata["deviations"])
        except Exception as e:
            val['error'] = "NoDataYet"
            logger.debug(f"Data was not avaliable for processing when getting attributes for sensor {self._name}")
            

        return val  
        
class HASLDeviationSensor(HASLDevice):
    """HASL Deviation Sensor class."""

    def __init__(self, hass, config, deviationtype, deviationkey):
        """Initialize."""
        self._config = config
        self._hass = hass
        self._deviationkey = deviationkey
        self._deviationtype = deviationtype
        self._enabled_sensor = config.options[CONF_SENSOR]
        self._name = f"SL {self._deviationtype.capitalize()} Deviation Sensor {self._deviationkey} ({self._config.title})"
        self._sensordata = []
        self._enabled_sensor
        self._scan_interval = self._config.options[CONF_SCAN_INTERVAL] or 300
        self._worker = hass.data[DOMAIN]["worker"]
        
    async def async_update(self):
        """Update the sensor."""

        logger.debug("[async_update] Entered")
        logger.debug(f"[async_update] Processing {self._name}")
        if self._worker.data.si2[f"{self._deviationtype}_{self._deviationkey}"]["api_lastrun"]:
            if self._worker.checksensorstate(self._enabled_sensor,STATE_ON):
                if self._worker.getminutesdiff(now().strftime('%Y-%m-%d %H:%M:%S'), self._worker.data.si2[f"{self._deviationtype}_{self._deviationkey}"]["api_lastrun"]) > self._config.options[CONF_SCAN_INTERVAL]:
                    try:
                        await self._worker.process_si2()
                        logger.debug("[async_update] Update processed")
                    except Exception as e:
                        logger.debug("[async_update] Error occured during update")
                else:
                    logger.debug("[async_update] Not due for update, skipping")

                    
        self._sensordata = self._worker.data.si2[f"{self._deviationtype}_{self._deviationkey}"]
        logger.debug("[async_update] Completed")               
        return

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"sl-deviation-{self._deviationtype}-{self._deviationkey}-sensor-{self._config.data[CONF_INTEGRATION_ID]}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensordata == []:
            return 'Unknown'
        else:
            return len(self._sensordata["data"])

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:train"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ""

    @property
    def scan_interval(self):
        """Return the unique id."""
        return self._scan_interval

    @property
    def device_state_attributes(self):
        """ Return the sensor attributes."""
        
        val = {}
        
        if self._sensordata == []:
            return val        
                
        if self._sensordata["api_result"] == "Success":
            val['api_result'] = "Ok"
        else:
            val['api_result'] = self._sensordata["api_error"]

        # Set values of the sensor.
        val['scan_interval'] = self._scan_interval
        val['refresh_enabled'] = self._worker.checksensorstate(self._enabled_sensor,STATE_ON)
        try:
            val['attribution'] = self._sensordata["attribution"]
            val['deviations'] = self._sensordata["data"]
            val['last_refresh'] = self._sensordata["last_updated"]
            val['deviation_count'] = len(self._sensordata["data"])
        except Exception as e:
            val['error'] = "NoDataYet"
            logger.debug(f"Data was not avaliable for processing when getting attributes for sensor {self._name}")
        
        return val           
        
class HASLVehicleLocationSensor(HASLDevice):
    """HASL Train Location Sensor class."""

    def __init__(self, hass, config, vehicletype):
        """Initialize."""
        self._hass = hass
        self._config = config
        self._vehicletype = vehicletype
        self._enabled_sensor = config.options[CONF_SENSOR]
        self._name = f"SL {self._vehicletype} Location Sensor ({self._config.title})"
        self._sensordata = []
        self._scan_interval = self._config.options[CONF_SCAN_INTERVAL] or 300
        self._worker = hass.data[DOMAIN]["worker"]

    async def async_update(self):
        """Update the sensor."""

        logger.debug("[async_update] Entered")
        logger.debug(f"[async_update] Processing {self._name}")
        if self._worker.data.fp[self._vehicletype]["api_lastrun"]:
            if self._worker.checksensorstate(self._enabled_sensor,STATE_ON):
                if self._worker.getminutesdiff(now().strftime('%Y-%m-%d %H:%M:%S'), self._worker.data.fp[self._vehicletype]["api_lastrun"]) > self._config.options[CONF_SCAN_INTERVAL]:
                    try:
                        await self._worker.process_fp()
                        logger.debug("[async_update] Update processed")
                    except Exception as e:
                        logger.debug("[async_update] Error occured during update")
                else:
                    logger.debug("[async_update] Not due for update, skipping")

        self._sensordata = self._worker.data.fp[self._vehicletype]
        logger.debug("[async_update] Completed")                
        return

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"sl-fl-{self._vehicletype}-sensor-{self._config.data[CONF_INTEGRATION_ID]}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensordata == []:
            return 'Unknown'
        else:
            return len(self._sensordata["data"])

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:train"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ""

    @property
    def scan_interval(self):
        """Return the unique id."""
        return self._scan_interval

    @property
    def device_state_attributes(self):
        
        val = {}
        
        if self._sensordata == []:
            return val
                      
        if self._sensordata["api_result"] == "Success":
            val['api_result'] = "Success"
        else:
            val['api_result'] = self._sensordata["api_error"]

        # Set values of the sensor.
        val['scan_interval'] = self._scan_interval
        val['refresh_enabled'] = self._worker.checksensorstate(self._enabled_sensor,STATE_ON)
        try:
            val['attribution'] = self._sensordata["attribution"]
            val['data'] = self._sensordata["data"]
            val['last_refresh'] = self._sensordata["last_updated"]
            val['vehicle_count'] = len(self._sensordata["data"])
        except Exception as e:
            val['error'] = "NoDataYet"
            logger.debug(f"Data was not avaliable for processing when getting attributes for sensor {self._name}")
        
        return val           
     

class HASLTrafficStatusSensor(HASLDevice):
    """HASL Traffic Status Sensor class."""

    def __init__(self, hass, config, sensortype):
        """Initialize."""
        self._hass = hass
        self._config = config
        self._sensortype = sensortype
        self._enabled_sensor = config.options[CONF_SENSOR]
        self._name = f"SL {self._sensortype.capitalize()} Status Sensor ({self._config.title})"
        self._sensordata = []
        self._scan_interval = self._config.options[CONF_SCAN_INTERVAL] or 300
        self._worker = hass.data[DOMAIN]["worker"]

    async def async_update(self):
        """Update the sensor."""

        logger.debug("[async_update] Entered")
        logger.debug(f"[async_update] Processing {self._name}")
        if self._worker.data.tl2[self._config.options[CONF_TL2_KEY]]["api_lastrun"]:
            if self._worker.checksensorstate(self._enabled_sensor,STATE_ON):
                if self._worker.getminutesdiff(now().strftime('%Y-%m-%d %H:%M:%S'), self._worker.data.tl2[self._config.options[CONF_TL2_KEY]]["api_lastrun"]) > self._config.options[CONF_SCAN_INTERVAL]:
                    try:
                        await self._worker.process_tl2()
                        logger.debug("[async_update] Update processed")
                    except Exception as e:
                        logger.debug("[async_update] Error occured during update")
                else:
                    logger.debug("[async_update] Not due for update, skipping")

                    
        self._sensordata = self._worker.data.tl2[self._config.options[CONF_TL2_KEY]]
        logger.debug("[async_update] Completed")               
        return

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"sl-{self._sensortype}-sensor-{self._config.data[CONF_INTEGRATION_ID]}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensordata == []:
            return 'Unknown'
        else:
            return self._sensordata["data"][self._sensortype]["status"]

    @property
    def icon(self):
        trafficTypeIcons = {
            'ferry': 'mdi:ferry',
            'bus': 'mdi:bus',
            'tram': 'mdi:tram',
            'train': 'mdi:train',
            'local': 'mdi:train-variant',
            'metro': 'mdi:subway-variant'
        } 

        return trafficTypeIcons.get(self._sensortype)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ""

    @property
    def scan_interval(self):
        """Return the unique id."""
        return self._scan_interval
        
    @property
    def device_state_attributes(self):
        
        val = {}
        
        if self._sensordata == []:
            return val
                    
        if self._sensordata["api_result"] == "Success":
            val['api_result'] = "Ok"
        else:
            val['api_result'] = self._sensordata["api_error"]

        # Set values of the sensor.
        val['scan_interval'] = self._scan_interval
        val['refresh_enabled'] = self._worker.checksensorstate(self._enabled_sensor,STATE_ON)

        try:
            val['attribution'] = self._sensordata["attribution"]
            val['status_icon'] = self._sensordata["data"][self._sensortype]["status_icon"]
            val['events'] = self._sensordata["data"][self._sensortype]["events"]        
            val['last_updated'] = self._sensordata["last_updated"]
        except Exception as e:
            val['error'] = "NoDataYet"
            logger.debug(f"Data was not avaliable for processing when getting attributes for sensor {self._name}")

        return val
        
