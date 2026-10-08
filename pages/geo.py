"""Place calendar events on the U.S. map shown under the Competition Calendar.

Event locations are free-text venue strings. ``short_location`` reduces a
venue to "City, ST", which is looked up, in order, in:

1. ``CITY_COORDS`` below, the cities contests have been held in;
2. ``GeocodedLocation`` rows, filled automatically from OpenStreetMap
   (Nominatim) whenever a calendar event is saved with a new city, and by
   ``manage.py geocode_locations``;
3. the state's center (flagged ``approximate``), so a contest still shows
   while a lookup is pending or has failed.

Events with no location at all are left off the map.

Points are projected with the same Albers USA (lower 48) projection the state
outlines in ``templates/partials/us_states_paths.svg`` were drawn with
(us-atlas ``states-albers-10m``: d3.geoAlbersUsa, scale 1300, translate
[487.5, 305], in a 975 x 610 viewBox).
"""
import json
import logging
import math
import threading
import time
import urllib.parse
import urllib.request

from .models import GeocodedLocation, short_location

logger = logging.getLogger(__name__)

MAP_WIDTH = 975
MAP_HEIGHT = 610

# "City, ST" (as produced by short_location) -> (latitude, longitude).
CITY_COORDS = {
    'Abingdon, VA': (36.709, -81.977),
    'Beaver, WV': (37.748, -81.143),
    'Beckley, WV': (37.778, -81.188),
    'Birmingham, AL': (33.519, -86.810),
    'Blacksburg, VA': (37.229, -80.414),
    'Bluefield, WV': (37.270, -81.222),
    'Cadiz, OH': (40.273, -80.997),
    'Carlsbad, NM': (32.421, -104.229),
    'Carmichaels, PA': (39.898, -79.976),
    'Caryville, TN': (36.298, -84.221),
    'Caryville (Cove Lake), TN': (36.304, -84.213),
    'Cove Lake, TN': (36.304, -84.213),
    'Cedar Bluff, VA': (37.087, -81.759),
    'Clymer, NY': (42.060, -79.730),
    'Craig, CO': (40.515, -107.546),
    'Cumberland, KY': (36.978, -82.988),
    'Dandridge, TN': (36.015, -83.415),
    'Delta, CO': (38.742, -108.069),
    'Elko, NV': (40.832, -115.763),
    'Farmington, MO': (37.781, -90.422),
    'Farmington, NM': (36.728, -108.219),
    'Fort Branch, IN': (38.251, -87.581),
    'Franklin, TN': (35.925, -86.869),
    'Gillette, WY': (44.291, -105.502),
    'Golden, CO': (39.756, -105.221),
    'Harlan, KY': (36.843, -83.322),
    'Harrisburg, IL': (37.738, -88.540),
    'Havana, FL': (30.624, -84.414),
    'Hazard, KY': (37.250, -83.193),
    'Hutchinson, KS': (38.061, -97.930),
    'Kellogg, ID': (47.538, -116.119),
    'Knoxville, TN': (35.961, -83.921),
    'Lakewood, CO': (39.705, -105.081),
    'Lexington, KY': (38.040, -84.503),
    'Logan, WV': (37.849, -81.994),
    'Logan/Chapmanville, WV': (37.910, -82.005),
    'Loveland, CO': (40.398, -105.075),
    'Madisonville, KY': (37.328, -87.499),
    'Marion, IL': (37.731, -88.933),
    'Pavilion of Marion, IL': (37.731, -88.933),
    'Maysville, KY': (38.641, -83.744),
    'Morgantown, WV': (39.630, -79.956),
    'Moundsville, WV': (39.920, -80.743),
    'New Iberia, LA': (30.004, -91.819),
    'Pikeville, KY': (37.479, -82.519),
    'Prestonsburg, KY': (37.666, -82.772),
    'Price, UT': (39.599, -110.811),
    'Rochester, NY': (43.157, -77.616),
    'Rock Springs, WY': (41.587, -109.203),
    'Rolla, MO': (37.952, -91.771),
    'Ruff Creek, PA': (39.938, -80.161),
    'Ruidoso, NM': (33.332, -105.673),
    'Ruidoso/Mescalero, NM': (33.240, -105.740),
    'Sevierville, TN': (35.868, -83.562),
    'Sumiton, AL': (33.756, -87.050),
    'Sylvester, WV': (37.987, -81.554),
    'Tallahassee, FL': (30.438, -84.281),
    'Tuscaloosa, AL': (33.210, -87.569),
    'Vincennes, IN': (38.677, -87.529),
    'Waynesburg, PA': (39.896, -80.179),
    'Wilmington, IL': (41.308, -88.147),
    'Winnemucca, NV': (40.973, -117.736),
    'Wise, VA': (36.976, -82.576),
}

# Rough geographic centers of the lower 48, for cities not in CITY_COORDS.
STATE_CENTERS = {
    'AL': (32.8, -86.8), 'AZ': (34.3, -111.7), 'AR': (34.9, -92.4),
    'CA': (37.2, -119.5), 'CO': (39.0, -105.5), 'CT': (41.6, -72.7),
    'DE': (39.0, -75.5), 'FL': (28.6, -82.4), 'GA': (32.7, -83.4),
    'ID': (44.4, -114.6), 'IL': (40.0, -89.2), 'IN': (39.9, -86.3),
    'IA': (42.1, -93.5), 'KS': (38.5, -98.4), 'KY': (37.5, -85.3),
    'LA': (31.1, -92.0), 'ME': (45.4, -69.2), 'MD': (39.0, -76.8),
    'MA': (42.3, -71.8), 'MI': (44.3, -85.4), 'MN': (46.3, -94.3),
    'MS': (32.7, -89.7), 'MO': (38.4, -92.5), 'MT': (47.0, -109.6),
    'NE': (41.5, -99.8), 'NV': (39.3, -116.6), 'NH': (43.7, -71.6),
    'NJ': (40.2, -74.7), 'NM': (34.4, -106.1), 'NY': (42.9, -75.5),
    'NC': (35.6, -79.4), 'ND': (47.5, -100.5), 'OH': (40.3, -82.8),
    'OK': (35.6, -97.5), 'OR': (43.9, -120.6), 'PA': (40.9, -77.8),
    'RI': (41.7, -71.5), 'SC': (33.9, -80.9), 'SD': (44.4, -100.2),
    'TN': (35.9, -86.4), 'TX': (31.5, -99.3), 'UT': (39.3, -111.7),
    'VT': (44.1, -72.7), 'VA': (37.5, -78.9), 'WA': (47.4, -120.5),
    'WV': (38.6, -80.6), 'WI': (44.6, -89.9), 'WY': (43.0, -107.6),
}

# --- Albers USA (lower 48), matching d3.geoAlbersUsa().scale(1300) ---------
_SCALE = 1300
_TRANSLATE = (487.5, 305)
_ROTATE_LON = 96          # d3.geoAlbers rotate([96, 0])
_CENTER = (-0.6, 38.7)    # d3.geoAlbers center, in rotated coordinates
_PARALLELS = (29.5, 45.5)

_s0 = math.sin(math.radians(_PARALLELS[0]))
_N = (_s0 + math.sin(math.radians(_PARALLELS[1]))) / 2
_C = 1 + _s0 * (2 * _N - _s0)
_R0 = math.sqrt(_C) / _N


def _conic_equal_area(lam, phi):
    r = math.sqrt(_C - 2 * _N * math.sin(phi)) / _N
    lam *= _N
    return r * math.sin(lam), _R0 - r * math.cos(lam)


_CX, _CY = _conic_equal_area(math.radians(_CENTER[0]), math.radians(_CENTER[1]))


def project(lat, lng):
    """Latitude/longitude -> (x, y) in the 975 x 610 map viewBox."""
    lam = math.radians(((lng + _ROTATE_LON + 180) % 360) - 180)
    x, y = _conic_equal_area(lam, math.radians(lat))
    return (_TRANSLATE[0] + _SCALE * (x - _CX),
            _TRANSLATE[1] - _SCALE * (y - _CY))


def is_surface(event):
    """Surface contests always say so in the title ("Surface Mine Rescue
    Contest", "Nevada Safety Olympiad (Surface)"); everything else is an
    underground contest."""
    return 'surface' in event.title.lower()


def _geocoded():
    return {q: (lat, lng) for q, lat, lng in
            GeocodedLocation.objects.values_list('query', 'latitude', 'longitude')}


def locate(location, geocoded=None):
    """Venue string -> (label, (lat, lng), approximate) or None.

    ``geocoded`` is a preloaded {query: (lat, lng)} of GeocodedLocation rows
    (loaded here when not given)."""
    label = short_location(location).strip()
    if not label:
        return None
    if label in CITY_COORDS:
        return label, CITY_COORDS[label], False
    if geocoded is None:
        geocoded = _geocoded()
    if label in geocoded:
        return label, geocoded[label], False
    state = label.rsplit(', ', 1)[-1] if ', ' in label else ''
    if state in STATE_CENTERS:
        return label, STATE_CENTERS[state], True
    return None


# --- Automatic lookup of new cities ----------------------------------------
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'MineRescueCenter/1.0 (+https://minerescuecenter.com)'
# The map only draws the lower 48; ignore matches outside it.
_LOWER48 = {'lat': (24.0, 49.6), 'lng': (-125.0, -66.5)}
_lookup_lock = threading.Lock()
_last_lookup = 0.0


def _nominatim(query):
    """Return (lat, lng) for ``query`` or None. Rate-limited to one request a
    second, as Nominatim's usage policy requires."""
    global _last_lookup
    params = urllib.parse.urlencode({
        'q': query, 'format': 'json', 'limit': 1, 'countrycodes': 'us',
    })
    request = urllib.request.Request(f'{NOMINATIM_URL}?{params}',
                                     headers={'User-Agent': USER_AGENT})
    with _lookup_lock:
        wait = _last_lookup + 1.1 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                results = json.load(response)
        finally:
            _last_lookup = time.monotonic()
    if not results:
        return None
    lat, lng = float(results[0]['lat']), float(results[0]['lon'])
    if not (_LOWER48['lat'][0] <= lat <= _LOWER48['lat'][1]
            and _LOWER48['lng'][0] <= lng <= _LOWER48['lng'][1]):
        return None
    return lat, lng


def geocode_location(location):
    """Make sure ``location`` can be placed exactly on the map, looking its
    city up online if it's new. Returns the GeocodedLocation created, or None
    when nothing was needed or the lookup failed (it's retried on the next
    save, or by ``manage.py geocode_locations``). Never raises."""
    label = short_location(location).strip()
    if not label or label in CITY_COORDS:
        return None
    if GeocodedLocation.objects.filter(query=label).exists():
        return None
    try:
        coords = _nominatim(label)
        if coords is None and label != location.strip():
            coords = _nominatim(location.strip())  # try the full venue
    except Exception:
        logger.warning('Geocoding %r failed', label, exc_info=True)
        return None
    if coords is None:
        logger.info('No map location found for %r', label)
        return None
    place, _ = GeocodedLocation.objects.get_or_create(
        query=label, defaults={'latitude': coords[0], 'longitude': coords[1]})
    return place


# Dots closer than this (in viewBox units) merge into one marker so nearby
# towns (Beckley/Beaver, Logan/Chapmanville) stay clickable.
CLUSTER_RADIUS = 11


def map_markers(events):
    """Group events into clickable map markers.

    Returns ``(markers, unmapped)``. Each marker is a dict with ``x``, ``y``,
    ``count`` and ``places`` (``[{'label', 'approximate', 'events'}]``), where
    events keep the order given. ``unmapped`` lists events whose location
    couldn't be placed."""
    places = {}
    unmapped = []
    geocoded = _geocoded()
    for event in events:
        found = locate(event.location, geocoded)
        if not found:
            unmapped.append(event)
            continue
        label, (lat, lng), approximate = found
        place = places.get(label)
        if place is None:
            x, y = project(lat, lng)
            place = places[label] = {
                'label': label, 'approximate': approximate,
                'x': x, 'y': y, 'events': [],
            }
        place['events'].append(event)

    markers = []
    for place in places.values():
        for marker in markers:
            if math.hypot(marker['x'] - place['x'], marker['y'] - place['y']) <= CLUSTER_RADIUS:
                marker['places'].append(place)
                break
        else:
            markers.append({'x': place['x'], 'y': place['y'], 'places': [place]})

    for marker in markers:
        n = len(marker['places'])
        marker['x'] = round(sum(p['x'] for p in marker['places']) / n, 1)
        marker['y'] = round(sum(p['y'] for p in marker['places']) / n, 1)
        marker['count'] = sum(len(p['events']) for p in marker['places'])
    return markers, unmapped
