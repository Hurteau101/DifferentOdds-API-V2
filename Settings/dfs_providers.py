from dataclasses import dataclass
from typing import Optional, Dict


# DFSProvider class to represent a DFS provider with its details.
@dataclass
class DFSProvider:
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None

# List of DFS providers with their configurations.
DFS_PROVIDERS = [
    DFSProvider(
        name="underdog",
        url={
            "main_url": "https://api.underdogfantasy.com/beta/v5/over_under_lines",
        },
        method="GET",
    ),
    DFSProvider(
        name="prizepicks",
        url={
            "main_url": "https://partner-api.prizepicks.com/projections"
        },
        method="GET"
    )
]