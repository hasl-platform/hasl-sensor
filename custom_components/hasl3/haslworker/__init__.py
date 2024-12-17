
import logging
from datetime import datetime

import isodate
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import now

from custom_components.hasl3.rrapi import rrapi_rra, rrapi_rrd, rrapi_rrr
from custom_components.hasl3.slapi import slapi_fp

logger = logging.getLogger("custom_components.hasl3.worker")


class HASLStatus(object):
    """System Status."""
    startup_in_progress = True
    running_background_tasks = False

class HASLData(object):
    rp3 = {}
    rp3keys = {}
    rrd = {}
    rra = {}
    rrr = {}
    rrkeys = {}
    fp = {}

    def dump(self):
        return {
            'rrkeys': self.rrkeys,
            'fp': self.fp,
            'rrd': self.rrd,
            'rra': self.rra,
            'rrr': self.rrr
        }


class HASLInstances(object):
    """The instance holder object object"""

    instances = {}
    instanceCount = 0

    def add(self, id, updater):
        self.instances[id] = {
            'subscriber': updater
        }
        self.instanceCount += 1

    def remove(self, id):
        try:
            self.instances[id]['subscriber']()
            self.instanceCount -= 1
            del self.instances[id]
        except Exception as e:
            logger.debug(
                f"Error occurred while deregistering listener {str(e)}")

    def count(self):
        return self.instanceCount


class HaslWorker(object):
    """HaslWorker."""

    hass: HomeAssistant | None = None

    status = HASLStatus()
    data = HASLData()
    instances = HASLInstances()

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    def getminutesdiff(self, d1, d2):
        d1 = datetime.strptime(d1, "%Y-%m-%d %H:%M:%S")
        d2 = datetime.strptime(d2, "%Y-%m-%d %H:%M:%S")
        diff = (d1 - d2).total_seconds()
        logger.debug(f"[get_minutes_diff] diff {diff}, d1 {d1}, d2 {d2}")
        return diff

    def checksensorstate(self, sensor, state, default=True):
        logger.debug("[check_sensor_state] Entered")
        if sensor is not None and not sensor == "":
            try:
                sensor_state = self.hass.states.get(sensor)
                if sensor_state.state is state:
                    logger.debug("[check_sensor_state] Completed will return TRUE/ENABLED")
                    return True
                else:
                    logger.debug("[check_sensor_state] Completed will return FALSE/DISABLED")
                    return False
            except:
                logger.debug("[check_sensor_state] An error occurred, default will be returned")
                return default
        else:
            logger.debug("[check_sensor_state] No sensor specified, will return default")
            return default

    async def assert_rp3(self, key, source, destination):
        logger.debug("[assert_rp3] Entered")

        listvalue = f"{source}-{destination}"
        if key not in self.data.rp3keys:
            logger.debug("[assert_rp3] Registered key")
            self.data.rp3keys[key] = {
                "api_key": key,
                "trips": ""
            }
        else:
            logger.debug("[assert_rp3] Key already present")

        currentvalue = self.data.rp3keys[key]['trips']
        if currentvalue == "":
            logger.debug("[assert_rp3] Creating trip key")
            self.data.rp3keys[key]["trips"] = listvalue
        else:
            logger.debug("[assert_rp3] Amending to trip key")
            self.data.rp3keys[key]["trips"] = f"{currentvalue}|{listvalue}"

        if listvalue not in self.data.rp3:
            logger.debug("[assert_rp3] Creating default values")
            self.data.rp3[listvalue] = {
                "api_type": "slapi-rp3",
                "api_lastrun": '1970-01-01 01:01:01',
                "api_result": "Pending",
                "trips": []
            }

        logger.debug("[assert_rp3] Completed")
        return

    def parseDepartureTime(self, t):
        """ weird time formats from the API,
        do some quick and dirty conversions. """

        try:
            if t == 'Nu':
                return 0
            s = t.split()
            if len(s) > 1 and s[1] == 'min':
                return int(s[0])
            s = t.split(':')
            if len(s) > 1:
                rightnow = now()
                min = int(s[0]) * 60 + int(s[1]) - (
                    (rightnow.hour * 60) + rightnow.minute)
                if min < 0:
                    min = min + 1440
                return min
        except:
            return
        return

    async def process_rp3(self):
        logger.debug("[process_rp3] Entered")
        return # Disabled for now

    async def assert_fp(self, traintype):
        logger.debug("[assert_fp] Entered")

        if traintype not in self.data.fp:
            logger.debug(f"[assert_fp] Registering {traintype}")
            self.data.fp[traintype] = {
                "api_type": "slapi-fp1",
                "api_lastrun": '1970-01-01 01:01:01',
                "api_result": "Pending"
            }
        else:
            logger.debug(f"[assert_fp] {traintype} already registered")

        logger.debug("[assert_fp] Completed")
        return

    async def process_fp(self, notarealarg=None):
        logger.debug("[process_rp3] Entered")

        api = slapi_fp()
        for traintype in list(self.data.fp):
            logger.debug(f"[process_rp3] Processing {traintype}")

            newdata = self.data.fp[traintype]
            try:
                newdata['data'] = await api.request(traintype)
                newdata['attribution'] = "Stockholms Lokaltrafik"
                newdata['last_updated'] = now().strftime('%Y-%m-%d %H:%M:%S')
                newdata['api_result'] = "Success"
                logger.debug(f"[process_rp3] Completed {traintype}")
            except Exception as e:
                newdata['api_result'] = "Error"
                newdata['api_error'] = str(e)
                logger.debug(f"[process_rp3] Error occurred for {traintype}: {str(e)}")

            newdata['api_lastrun'] = now().strftime('%Y-%m-%d %H:%M:%S')
            self.data.fp[traintype] = newdata
        logger.debug("[process_rp3] Completed")

    async def assert_rrd(self, key, stop):
        logger.debug("[assert_rrd] Entered")
        stopkey = str(stop)

        if key not in self.data.rrkeys:
            logger.debug("[assert_rrd] Registering key")
            self.data.rrkeys[key] = {
                "api_key": key
            }

        if 'deps' not in self.data.rrkeys[key]:
            logger.debug("[assert_rrd] Registering deps key")
            self.data.rrkeys[key]['deps'] = f"{stopkey}"
        else:
            logger.debug("[assert_rrd] Adding stop to existing deps key")
            self.data.rrkeys[key]["deps"] = f"{self.data.rrkeys[key]['deps']},{stopkey}"

        if stop not in self.data.rrd:
            logger.debug("[assert_rrd] Creating default data")
            self.data.rrd[stopkey] = {
                "api_type": "rrapi-rrd",
                "api_lastrun": '1970-01-01 01:01:01',
                "api_result": "Pending"
            }

        logger.debug("[assert_rrd] Completed")
        return

    async def assert_rra(self, key, stop):
        logger.debug("[assert_rra] Entered")
        stopkey = str(stop)

        if key not in self.data.rrkeys:
            logger.debug("[assert_rra] Registering key")
            self.data.rrkeys[key] = {
                "api_key": key
            }

        if 'arrs' not in self.data.rrkeys[key]:
            logger.debug("[assert_rra] Registering arrs key")
            self.data.rrkeys[key]['arrs'] = f"{stopkey}"
        else:
            logger.debug("[assert_rra] Adding stop to existing arrs key")
            self.data.rrkeys[key]["arrs"] = f"{self.data.rrkeys[key]['arrs']},{stopkey}"

        if stop not in self.data.rra:
            logger.debug("[assert_rra] Creating default data")
            self.data.rra[stopkey] = {
                "api_type": "rrapi-rra",
                "api_lastrun": '1970-01-01 01:01:01',
                "api_result": "Pending"
            }

        logger.debug("[assert_rra] Completed")
        return

    async def assert_rrr(self, key, source, destination):
        logger.debug("[assert_rrr] Entered")

        listvalue = f"{source}-{destination}"
        if key not in self.data.rrkeys:
            logger.debug("[assert_rra] Registering key")
            self.data.rrkeys[key] = {
                "api_key": key
            }

        if 'trips' not in self.data.rrkeys[key]:
            logger.debug("[assert_rra] Registering trips key")
            self.data.rrkeys[key]['trips'] = ""

        currentvalue = self.data.rrkeys[key]['trips']
        if currentvalue == "":
            logger.debug("[assert_rrr] Creating trip key")
            self.data.rrkeys[key]["trips"] = listvalue
        else:
            logger.debug("[assert_rrr] Amending to trip key")
            self.data.rrkeys[key]["trips"] = f"{currentvalue}|{listvalue}"

        if listvalue not in self.data.rrr:
            logger.debug("[assert_rrr] Creating default values")
            self.data.rrr[listvalue] = {
                "api_type": "rrapi-rrr",
                "api_lastrun": '1970-01-01 01:01:01',
                "api_result": "Pending",
                "trips": []
            }

        logger.debug("[assert_rp3] Completed")
        return

    async def process_rrd(self, notarealarg=None):
        logger.debug("[process_rrd] Entered")

        iconswitcher = {
            'BLT': 'mdi:bus',
            'BXB': 'mdi:bus',
            'ULT': 'mdi:subway-variant',
            'JAX': 'mdi:train',
            'JLT': 'mdi:train',
            'JRE': 'mdi:train',
            'JIC': 'mdi:train',
            'JPT': 'mdi:train',
            'JEX': 'mdi:train',
            'SLT': 'mdi:tram',
            'FLT': 'mdi:ferry',
            'FUT': 'mdi:ferry'
        }

        for rrkey in list(self.data.rrkeys):
            logger.debug(f"[process_rrd] Processing key {rrkey}")
            rrdata = self.data.rrkeys[rrkey]
            api = rrapi_rrd(rrkey, 60)
            for stop in ','.join(set(rrdata["deps"].split(','))).split(','):
                logger.debug(f"[process_rrd] Processing stop {stop}")
                newdata = self.data.rrd[stop]
                # TODO: CHECK FOR FRESHNESS TO NOT KILL OFF THE KEYS

                try:
                    departures = []
                    departuredata = await api.request(stop)
                    departuredata = departuredata['Departure']

                    for (idx, value) in enumerate(departuredata):

                        adjustedDateTime = now()
                        adjustedDateTime = adjustedDateTime.replace(tzinfo=None)
                        if 'rtDate' in value and 'rtTime' in value:
                            diff = datetime.strptime(f'{value["rtDate"]} {value["rtTime"]}', '%Y-%m-%d %H:%M:%S') - adjustedDateTime
                            expected = datetime.strptime(f'{value["rtDate"]} {value["rtTime"]}', '%Y-%m-%d %H:%M:%S')
                        else:
                            diff = datetime.strptime(f'{value["date"]} {value["time"]}', '%Y-%m-%d %H:%M:%S') - adjustedDateTime
                            expected = datetime.strptime(f'{value["date"]} {value["time"]}', '%Y-%m-%d %H:%M:%S')
                        diff = diff.total_seconds()
                        diff = diff / 60
                        diff = round(diff)

                        departures.append({
                            'line': value["ProductAtStop"]["displayNumber"],
                            'direction': value["directionFlag"],
                            'departure': datetime.strptime(f'{value["date"]} {value["time"]}', '%Y-%m-%d %H:%M:%S'),
                            'destination': value["direction"],
                            'time': diff,
                            'operator': value["ProductAtStop"]["operator"],
                            'expected': expected,
                            'type': value["ProductAtStop"]["catOut"],
                            'icon': iconswitcher.get(value["ProductAtStop"]["catOut"],'mdi:train-car'),
                        })

                    newdata['data'] = sorted(departures,
                                                key=lambda k: k['time'])
                    newdata['attribution'] = "Samtrafiken Resrobot"
                    newdata['last_updated'] = now().strftime('%Y-%m-%d %H:%M:%S')
                    newdata['api_result'] = "Success"
                    logger.debug(f"[process_rrd] Stop {stop} updated successfully")

                except Exception as e:
                    newdata['api_result'] = "Error"
                    newdata['api_error'] = str(e)
                    logger.debug(f"[process_rrd] Error occurred during update {stop}")


                newdata['api_lastrun'] = now().strftime('%Y-%m-%d %H:%M:%S')
                self.data.rrd[stop] = newdata
                logger.debug(f"[process_rrd] Completed stop {stop}")

            logger.debug(f"[process_rrd] Completed key {rrkey}")

        logger.debug("[process_rrd] Completed")
        return

    async def process_rra(self, notarealarg=None):
        logger.debug("[process_rra] Entered")

        iconswitcher = {
            'BLT': 'mdi:bus',
            'BXB': 'mdi:bus',
            'ULT': 'mdi:subway-variant',
            'JAX': 'mdi:train',
            'JLT': 'mdi:train',
            'JRE': 'mdi:train',
            'JIC': 'mdi:train',
            'JPT': 'mdi:train',
            'JEX': 'mdi:train',
            'SLT': 'mdi:tram',
            'FLT': 'mdi:ferry',
            'FUT': 'mdi:ferry'
        }

        for rrkey in list(self.data.rrkeys):
            logger.debug(f"[process_rra] Processing key {rrkey}")
            rrdata = self.data.rrkeys[rrkey]
            api = rrapi_rra(rrkey, 60)
            for stop in ','.join(set(rrdata["arrs"].split(','))).split(','):
                logger.debug(f"[process_rra] Processing stop {stop}")
                newdata = self.data.rra[stop]
                # TODO: CHECK FOR FRESHNESS TO NOT KILL OFF THE KEYS

                try:
                    arrivals = []
                    arrivaldata = await api.request(stop)
                    arrivaldata = arrivaldata['Arrival']

                    logger.error(arrivaldata)

                    for (idx, value) in enumerate(arrivaldata):

                        adjustedDateTime = now()
                        adjustedDateTime = adjustedDateTime.replace(tzinfo=None)
                        if 'rtDate' in value and 'rtTime' in value:
                            diff = datetime.strptime(f'{value["rtDate"]} {value["rtTime"]}', '%Y-%m-%d %H:%M:%S') - adjustedDateTime
                            expected = datetime.strptime(f'{value["rtDate"]} {value["rtTime"]}', '%Y-%m-%d %H:%M:%S')
                        else:
                            diff = datetime.strptime(f'{value["date"]} {value["time"]}', '%Y-%m-%d %H:%M:%S') - adjustedDateTime
                            expected = datetime.strptime(f'{value["date"]} {value["time"]}', '%Y-%m-%d %H:%M:%S')
                        diff = diff.total_seconds()
                        diff = diff / 60
                        diff = round(diff)

                        arrivals.append({
                            'line': value["ProductAtStop"]["displayNumber"],
                            'arrival': datetime.strptime(f'{value["date"]} {value["time"]}', '%Y-%m-%d %H:%M:%S'),
                            'origin': value["origin"],
                            'time': diff,
                            'operator': value["ProductAtStop"]["operator"],
                            'expected': expected,
                            'type': value["ProductAtStop"]["catOut"],
                            'icon': iconswitcher.get(value["ProductAtStop"]["catOut"],'mdi:train-car'),
                        })

                    newdata['data'] = sorted(arrivals,
                                                key=lambda k: k['time'])
                    newdata['attribution'] = "Samtrafiken Resrobot"
                    newdata['last_updated'] = now().strftime('%Y-%m-%d %H:%M:%S')
                    newdata['api_result'] = "Success"
                    logger.debug(f"[process_rra] Stop {stop} updated successfully")

                except Exception as e:
                    newdata['api_result'] = "Error"
                    newdata['api_error'] = str(e)
                    logger.debug(f"[process_rra] Error occurred during update {stop}")


                newdata['api_lastrun'] = now().strftime('%Y-%m-%d %H:%M:%S')
                self.data.rra[stop] = newdata
                logger.debug(f"[process_rra] Completed stop {stop}")

            logger.debug(f"[process_rra] Completed key {rrkey}")

        logger.debug("[process_rra] Completed")
        return

    async def process_rrr(self):
        logger.debug("[process_rrr] Entered")

        for rrkey in list(self.data.rrkeys):
            logger.debug(f"[process_rrr] Processing key {rrkey}")
            rrdata = self.data.rrkeys[rrkey]
            api = rrapi_rrr(rrkey)
            for tripname in '|'.join(set(rrdata["trips"].split('|'))).split('|'):
                logger.debug(f"[process_rrr] Processing trip {tripname}")
                newdata = self.data.rrr[tripname]
                positions = tripname.split('-')

                try:

                    apidata = {}
                    srcLocID = positions[0]
                    dstLocID = positions[1]

                    apidata = await api.request(srcLocID, dstLocID)
                    newdata['trips'] = []

                    #Parse every trip
                    for trip in apidata["Trip"]:
                        newtrip = {
                            'legs': []
                        }

                        # Add legs to trips
                        for leg in trip['LegList']['Leg']:
                            newleg = {}
                            # Walking is done by humans.
                            # And robots.
                            # Robots are scary.
                            newleg['line'] = leg['Product'][0]['line'] if leg["type"] != "WALK" else "Walk"
                            newleg['direction'] = leg['directionFlag'] if leg["type"] != "WALK" else "Walk"
                            newleg['category'] = leg['type']
                            newleg['name'] = leg['Product'][0]['name']
                            newleg['from'] = leg['Origin']['name']
                            newleg['to'] = leg['Destination']['name']
                            newleg['time'] = f"{leg['Origin']['date']} {leg['Origin']['time']}"

                            if leg.get('Stops'):
                                if leg['Stops'].get('Stop', {}):
                                    newleg['stops'] = []
                                    for stop in leg.get('Stops', {}).get('Stop', {}):
                                        newleg['stops'].append(stop)

                            newtrip['legs'].append(newleg)

                        # Make some shortcuts for data
                        newtrip['first_leg'] = newtrip['legs'][0]['name']
                        newtrip['time'] = newtrip['legs'][0]['time']
                        newtrip['duration'] = str(isodate.parse_duration(trip['duration']))
                        newdata['trips'].append(newtrip)

                    # Add shortcuts to info in the first trip if it exists
                    firstLegFirstTrip = next((x for x in newdata['trips'][0]['legs'] if x["category"] != "WALK"), [])
                    lastLegLastTrip = next((x for x in reversed(newdata['trips'][0]['legs']) if x["category"] != "WALK"), [])
                    newdata['transfers'] = sum(p["category"] != "WALK" for p in newdata['trips'][0]['legs']) - 1 or 0
                    #newdata['price'] = newdata['trips'][0]['price'] or ''
                    newdata['time'] = newdata['trips'][0]['time'] or ''
                    newdata['duration'] = newdata['trips'][0]['duration'] or ''
                    newdata['from'] = newdata['trips'][0]['legs'][0]['from'] or ''
                    newdata['to'] = newdata['trips'][0]['legs'][len(newdata['trips'][0]['legs']) - 1]['to'] or ''
                    newdata['origin'] = {}
                    newdata['origin']['leg'] = firstLegFirstTrip["name"] or ''
                    newdata['origin']['line'] = firstLegFirstTrip["line"] or ''
                    newdata['origin']['direction'] = firstLegFirstTrip["direction"] or ''
                    newdata['origin']['category'] = firstLegFirstTrip["category"] or ''
                    newdata['origin']['time'] = firstLegFirstTrip["time"] or ''
                    newdata['origin']['from'] = firstLegFirstTrip["from"] or ''
                    newdata['origin']['to'] = firstLegFirstTrip["to"] or ''
                    newdata['destination'] = {}
                    newdata['destination']['leg'] = lastLegLastTrip["name"] or ''
                    newdata['destination']['line'] = lastLegLastTrip["line"] or ''
                    newdata['destination']['direction'] = lastLegLastTrip["direction"] or ''
                    newdata['destination']['category'] = lastLegLastTrip["category"] or ''
                    newdata['destination']['time'] = lastLegLastTrip["time"] or ''
                    newdata['destination']['from'] = lastLegLastTrip["from"] or ''
                    newdata['destination']['to'] = lastLegLastTrip["to"] or ''

                    newdata['attribution'] = "Samtrafiken Resrobot"
                    newdata['last_updated'] = now().strftime('%Y-%m-%d %H:%M:%S')
                    newdata['api_result'] = "Success"
                except Exception as e:
                    logger.debug(f"[process_rrr] Error occuredA: {str(e)}")
                    newdata['api_result'] = "Error"
                    newdata['api_error'] = str(e)

                newdata['api_lastrun'] = now().strftime('%Y-%m-%d %H:%M:%S')
                self.data.rrr[tripname] = newdata

                logger.debug(f"[process_rrr] Completed trip {tripname}")

            logger.debug(f"[process_rrr] Completed key {rrkey}")

        logger.debug("[process_rrr] Completed")
