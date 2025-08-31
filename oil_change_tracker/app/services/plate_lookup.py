import httpx
from ..core.config import PLATE_LOOKUP_PROVIDER, PLATE_LOOKUP_KEY, PLATE_LOOKUP_REGION

class PlateLookupError(Exception):
    pass

async def plate_to_vin(plate: str, state_or_region: str | None = None) -> str | None:
    """Return VIN (str) if found, else None.
    In demo mode (provider 'none'), returns a fake VIN for known sample plates.
    """
    plate = plate.strip().upper()
    provider = PLATE_LOOKUP_PROVIDER
    key = PLATE_LOOKUP_KEY
    region = state_or_region or PLATE_LOOKUP_REGION

    if provider == "none" or not key:
        # Demo behavior
        if plate in {"TEST123", "DEMO1", "SAMPLE"}:
            return "1FAFP404XWF123456"
        return None

    if provider == "abstract":
        # Example: AbstractAPI (placeholder; adjust to real endpoint)
        url = "https://ipdata.abstractapi.com/v1/placeholder_plate_endpoint"
        # You'll need to replace with a real provider that supports plate->VIN
        raise PlateLookupError("AbstractAPI placeholder: configure a real plate→VIN provider.")

    if provider == "vinapi":
        # Placeholder for any VIN API you wire via RapidAPI
        raise PlateLookupError("VIN API placeholder: configure RapidAPI provider and endpoint.")

    raise PlateLookupError(f"Unknown provider: {provider}")
