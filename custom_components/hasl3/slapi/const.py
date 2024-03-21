__version__ = '3.1.3'

FORDONSPOSITION_URL = 'https://api.sl.se/fordonspositioner/GetData?' \
                      'type={}&pp=false&cacheControl={}'

TRAFIKLAB_URL = 'https://journeyplanner.integration.sl.se/v1/'
PU1_URL = TRAFIKLAB_URL + 'typeahead.json?key={}&searchstring={}' \
                          '&stationsonly=False&maxresults=25'
RP3_URL = TRAFIKLAB_URL + 'TravelplannerV3_1/trip.json?key={}&originExtId={}' \
                          '&destExtId={}&originCoordLat={}' \
                          '&originCoordLong={}&destCoordLat={}' \
                          '&destCoordLong={}&Passlist=1'

USER_AGENT = "hasl-slapi/" + __version__
