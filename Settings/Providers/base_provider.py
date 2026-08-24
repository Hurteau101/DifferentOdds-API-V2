from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class BaseProvider:
    title: str
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None
    is_active: Optional[bool] = False
    curl_impersonation: Optional[str] = "chrome"
    alternate_name: Optional[str] = None
    has_sgp: bool = False