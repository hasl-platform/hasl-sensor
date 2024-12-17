import json
import logging
import time
from typing import Iterable, TypedDict

import aiohttp
import httpx
import isodate

from .const import FORDONSPOSITION_URL, USER_AGENT, __version__
from .exceptions import SLAPI_Error, SLAPI_HTTP_Error

logger = logging.getLogger(__name__)


class slapi_fp(object):
    def __init__(self, timeout=None):
        self._timeout = timeout

    def version(self):
        return __version__

    async def request(self, vehicletype):
        logger.debug("Will call FP API")
        if vehicletype not in (
            "PT",
            "RB",
            "TVB",
            "SB",
            "LB",
            "SpvC",
            "TB1",
            "TB2",
            "TB3",
        ):
            raise SLAPI_Error(
                -1,
                "Vehicle type is not valid",
                "Must be one of 'PT','RB','TVB','SB'," "'LB','SpvC','TB1','TB2','TB3'",
            )

        try:
            async with httpx.AsyncClient() as client:
                request = await client.get(
                    FORDONSPOSITION_URL.format(vehicletype, time.time()),
                    headers={"User-agent": USER_AGENT},
                    follow_redirects=True,
                    timeout=self._timeout,
                )
        except Exception as e:
            error = SLAPI_HTTP_Error(
                997, "An HTTP error occurred (Vehicle Locations)", str(e)
            )
            logger.debug(e)
            logger.error(error)
            raise error

        response = json.loads(request.json())

        result = []

        for trip in response["Trips"]:
            result.append(trip)

        logger.debug("Call completed")
        return result


RPTripRequest = (
    tuple[str | int, str | int]
    | tuple[str | float, str | float, str | float, str | float]
)


class Fare(TypedDict):
    name: str
    desc: str
    price: float


class Leg(TypedDict):
    name: str
    line: str
    direction: str
    category: str
    from_: str
    to: str
    time: str
    stops: list


class Trip(TypedDict):
    fares: list[Fare]
    legs: list[Leg]
    first_leg: str
    time: str
    price: float
    duration: str
    transfers: int


class SLRoutePlanner31TripApi:
    """
    https://www.trafiklab.se/api/trafiklab-apis/sl/route-planner-31/#trip

    TODO: move to external library
    """

    api_errors = {
        1001: "No API key supplied in request",
        1002: "The supplied API key is not valid",
        1003: "Specified API is not valid",
        1004: "The API is not available for this key",
        1005: "Key exists but is not for requested API",
        1006: "Too many request per minute (quota exceeded for key)",
        1007: "Too many request per month (quota exceeded for key)",
        4002: "Date filter is not valid",
        5000: "Parameter invalid",
    }

    def __init__(self, api_key: str, session: aiohttp.ClientSession):
        self._api_key = api_key
        self._session = session

    async def request(
        self,
        request: RPTripRequest,
    ):
        params = {
            "key": self._api_key,
            "Passlist": 1,
        }
        if len(request) == 2:
            origin, destination = request
            params.update(
                {
                    "originExtId": origin,
                    "destExtId": destination,
                }
            )
        elif len(request) == 4:
            orgLat, orgLong, destLat, destLong = request
            params.update(
                {
                    "originCoordLat": orgLat,
                    "originCoordLong": orgLong,
                    "destCoordLat": destLat,
                    "destCoordLong": destLong,
                }
            )
        else:
            raise ValueError("Invalid request")

        resp = await self._session.get(
            "https://journeyplanner.integration.sl.se/v1/TravelplannerV3_1/trip.json",
            params=params,
            headers={"User-agent": USER_AGENT},
        )
        resp.raise_for_status()

        jsonResponse = await resp.json()
        if not jsonResponse:
            raise SLAPI_Error(999, "Internal error", "jsonResponse is empty")

        if "Trip" not in jsonResponse:
            logger.debug(jsonResponse)
            raise SLAPI_Error(-100, "ResponseType not as expected")

        return jsonResponse

    def transform(self, response: dict) -> dict:
        """
        Transform response to a more readable format
        """

        def _parse_leg(leg) -> Leg:
            is_walk = leg["type"] == "WALK"
            # Walking is done by humans.
            # And robots.
            # Robots are scary.

            name = leg["name"] if is_walk else leg["Product"]["name"]
            line = "Walk" if is_walk else leg["Product"]["line"]
            direction = "Walk" if is_walk else leg["direction"]
            category = "WALK" if is_walk else leg["category"]

            return Leg(
                {
                    "name": name,
                    "line": line,
                    "direction": direction,
                    "category": category,
                    "from": leg["Origin"]["name"],
                    "to": leg["Destination"]["name"],
                    "time": f"{leg['Origin']['date']} {leg['Origin']['time']}",
                    # "stops": leg.get("Stops", {}).get("Stop", []),
                }
            )

        def _parse_trip(trip) -> Trip:
            # Loop all fares and add
            fares = [
                Fare(
                    {
                        "name": fare["name"],
                        "desc": fare.get("desc", ""),
                        "price": int(fare["price"]) / 100,
                    }
                )
                for fare in trip["TariffResult"]["fareSetItem"][0]["fareItem"]
            ]

            # Add legs to trips
            legs = [_parse_leg(leg) for leg in trip["LegList"]["Leg"]]

            # Make some shortcuts for data
            first_leg = next(iter(legs), None)
            first_fare = next(iter(fares), None)
            if trip_duration := trip.get("duration"):
                trip_duration = str(isodate.parse_duration(trip_duration))

            return Trip(
                {
                    "fares": fares,
                    "legs": legs,
                    "first_leg": first_leg and first_leg["name"],
                    "time": first_leg and first_leg["time"],
                    "price": first_fare and first_fare["price"],
                    "duration": trip_duration,
                    "transfers": trip.get("transferCount", 0),
                }
            )

        newdata = {}

        # Parse every trip
        trips = [_parse_trip(trip) for trip in response["Trip"]]
        newdata["trips"] = [x for x in trips]

        def _first_non_walk_leg(legs: Iterable[Leg]):
            return next((x for x in legs if x["category"] != "WALK"), None)

        # Add shortcuts to info in the first trip if it exists
        if firstTrip := next(iter(trips), None):
            if firstLegFirstTrip := _first_non_walk_leg(firstTrip["legs"]):
                newdata["origin"] = firstLegFirstTrip

            if lastLedLastTrip := _first_non_walk_leg(reversed(firstTrip["legs"])):
                newdata["destination"] = lastLedLastTrip

            newdata["transfers"] = (
                sum(leg["category"] != "WALK" for leg in firstTrip["legs"]) - 1 or 0
            )
            newdata["price"] = firstTrip["price"]
            newdata["time"] = firstTrip["time"]
            newdata["duration"] = firstTrip["duration"]
            newdata["from"] = firstLegFirstTrip and firstLegFirstTrip["from"]
            newdata["to"] = lastLedLastTrip and lastLedLastTrip["to"]

        return newdata
