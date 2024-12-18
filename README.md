![maintained](https://img.shields.io/maintenance/yes/2024.svg)
[![hacs_badge](https://img.shields.io/badge/hacs-default-green.svg)](https://github.com/custom-components/hacs)
[![ha_version](https://img.shields.io/badge/home%20assistant-2024.4%2B-green.svg)](https://www.home-assistant.io)
![version](https://img.shields.io/badge/version-3.2.0b0-yellow.svg)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Swedish Public Transport Sensor (HASL)
======================================

## Project formerly known as "Home Assistant SL integration"

This is an Home Assistant integration providing sensors for [Stockholms Lokaltrafik (SL)](https://sl.se/) primarily, though it does support [Resrobot](https://resrobot.se/) and journeys in the whole country. This integration provides intelligent sensors for departures, deviations, vehicle locations, traffic status and route monitoring using the SL official APIs and departures, arrivals and route monitoring using Resrobot. It also provides services for Location ID lookup and Trip Planing. You will still need to get your own API keys from SL / Trafiklab (see docs for [HASL](https://hasl.sorlov.com)) for *some* of the API endpoints.

Full and detailed documentation [is available](http://hasl.sorlov.com).

## Install using HACS

* If you haven't already, you must have [HACS installed](https://hacs.xyz/docs/setup/download).
* Go into _HACS_ and search for _HASL_ under the _Integrations_ headline. Install the integration.
  * You will need to restart Home Assistant to finish the process.
* Once that is done reload your GUI (caching issues preventing the integration to be shown).
* Go to _Integrations_ and add _HASL integrations_.
  * For some of the integrations you might needd to obtain an API key from TrafikLab. Read details in [documentation](https://hasl.sorlov.com/trafiklab)
  * For some integrations you might need to enter [Location IDs](https://hasl.sorlov.com/locationid). You can use `sl_find_location` service for this

* Perhaps add some GUI/Lovelace components as examples shows in the [documentation](https://hasl.sorlov.com/lovelace_cards)
* Enjoy!

## Visualization

### [TEMPORARY] v3.2.0b+

While in beta, only the [HASL Departure Card v4](https://github.com/NecroKote/HA-hasl3-departure-card) is available
![HASL Departure Card v4](https://private-user-images.githubusercontent.com/1721257/313788625-2a4208f1-9007-4888-b084-32468d734a3c.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3MzQ1MjgwODUsIm5iZiI6MTczNDUyNzc4NSwicGF0aCI6Ii8xNzIxMjU3LzMxMzc4ODYyNS0yYTQyMDhmMS05MDA3LTQ4ODgtYjA4NC0zMjQ2OGQ3MzRhM2MucG5nP1gtQW16LUFsZ29yaXRobT1BV1M0LUhNQUMtU0hBMjU2JlgtQW16LUNyZWRlbnRpYWw9QUtJQVZDT0RZTFNBNTNQUUs0WkElMkYyMDI0MTIxOCUyRnVzLWVhc3QtMSUyRnMzJTJGYXdzNF9yZXF1ZXN0JlgtQW16LURhdGU9MjAyNDEyMThUMTMxNjI1WiZYLUFtei1FeHBpcmVzPTMwMCZYLUFtei1TaWduYXR1cmU9ODI2ZTM5OGZlMjgzNmE3ZWE0ZTFmY2U3NGVhZTUyNzRkMTEwMDQ3ODFmZWQ5MTMzMGQyYjNkMGE1YzYyNjdhMSZYLUFtei1TaWduZWRIZWFkZXJzPWhvc3QifQ.EgZQsRZhzjP_GDrMaPyBGXs7V1kZ_oTFUXQcyXAE11c)

The "Disruptions" card is currently in development

### legacy versions

The sensors should be able to be used multiple cards in hasl-cards ([departure-card](https://github.com/hasl-platform/lovelace-hasl-departure-card), [traffic-status-card](https://github.com/hasl-platform/lovelace-hasl-traffic-status-card)) . There are several cards for different sensors and presentation options for each sensor type. [More examples](https://hasl.sorlov.com/lovelace_cards) can be found in the [documentation](https://hasl.sorlov.com/).

![card](https://user-images.githubusercontent.com/8133650/56198334-0a150f00-603b-11e9-9e93-92be212d7f7b.PNG)


## Support the developers

If you enjoy this integration, consider supporting the developers to help keep it running smoothly and enhance future updates.

- [@DSorlov](https://www.buymeacoffee.com/sorlov) - author of the original
- [@NecroKote](https://buymeacoffee.com/mkukhta) - maintainer
