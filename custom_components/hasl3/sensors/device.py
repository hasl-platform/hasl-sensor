from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .. import const


SL_TRAFFIK_DEVICE_INFO = DeviceInfo(
    entry_type=DeviceEntryType.SERVICE,
    identifiers={(const.DOMAIN, const.SL_TRAFIK_DEVICE_GUID)},
    manufacturer=const.DEVICE_MANUFACTURER,
    model=const.DEVICE_MODEL,
    name=const.SL_TRAFIK_DEVICE_NAME,
    sw_version=const.HASL_VERSION,
)
