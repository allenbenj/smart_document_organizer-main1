from typing import Any, Optional

from fastapi import Request  # noqa: E402


def get_services(request: Request) -> Optional[Any]:
    return getattr(request.app.state, "services", None)


async def get_service(request: Request, key: str) -> Optional[Any]:
    services = get_services(request)
    if services is None or not hasattr(services, "get_service"):
        return None
    try:
        return await services.get_service(key)
    except Exception:
        return None


async def get_config(request: Request) -> Optional[Any]:
    return await get_service(request, "config_manager")
