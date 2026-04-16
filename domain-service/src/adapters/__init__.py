from typing import List, Type
from src.adapters.base import RegistrarAdapter
from src.adapters.namecheap import NamecheapAdapter
from src.adapters.godaddy import GoDaddyAdapter
from src.adapters.letshost import LetsHostAdapter
from src.adapters.cloudflare import CloudflareAdapter

DEFAULT_ADAPTERS: List[Type[RegistrarAdapter]] = [
    NamecheapAdapter,
    GoDaddyAdapter,
    LetsHostAdapter,
    CloudflareAdapter,
]

__all__ = [
    "RegistrarAdapter",
    "NamecheapAdapter",
    "GoDaddyAdapter",
    "LetsHostAdapter",
    "CloudflareAdapter",
    "DEFAULT_ADAPTERS",
]
