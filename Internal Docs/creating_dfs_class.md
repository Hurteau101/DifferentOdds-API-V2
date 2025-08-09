# Creating DFS Class with Inheritance

This document demonstrates how to create a starting DFS class which inherits the `DFSBookBase`


---

##### Ensure you create a DFS Provider in the `Settings.dfs_providers.py` file.

### Creating Provider
```python
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
        name="BookName",
        url={
            "main_url": "BookURL",
        },
        method="GET",
    )
]
```

### Creating DFS Class

```python
from Settings.dfs_book_base import DFSBookBase
from Settings.book_base import SportbookRequestType

class ExampleClass(DFSBookBase):
    def __init__(self):
        # SportbookRequestType can be either `Spoof` or `ASYNC`
        super().__init__(SportbookRequestType.SPOOF, sportsbook_name="Test")
```

### Custom Logging
#### If you do not set one in the `super().__init`, there will be a default `DFS Logs' directory created and the class name will be the log name.
```python
from Settings.dfs_book_base import DFSBookBase
from Settings.book_base import SportbookRequestType

class ExampleClass(DFSBookBase):
    def __init__(self):
        # SportbookRequestType can be either `Spoof` or `ASYNC`
        super().__init__(
            SportbookRequestType.SPOOF, 
            sportsbook_name="Test",
            log_directory="Test",  # This will create a directory
            log_name="test.log" # This will set a name for the log file
        )


```
