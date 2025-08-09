# API Caller Usage Examples

This document contains example calls to `api_caller` in `Settings.book_base.py`, demonstrating different usage patterns including spoofing, proxies, and asynchronous calls.

---

### Spoof API Call

```python
async def example(self):
    api_data = await self.api_caller(
        url=self.book_data.url.get("main_url"),
        method=self.book_data.method,
        client_identifier="chrome_114"
    )
```

### Spoof API Call with Proxy
```python
from Settings.proxy_manger import ProxyManager

async def example(self):
    proxy_manager = ProxyManager(self.api_caller)
    data = await proxy_manager.proxy_controller(
        url=self.book_data.url.get("main_url"),
        method=self.book_data.method,
        client_identifier="chrome_114",
        sync_type="spoof"
    )
```

### Async API Call

```python
import aiohttp

async def example(self):
    async with aiohttp.ClientSession() as session:
        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("main_url"),
            method=self.book_data.method
        )
```

### Async API Call with Proxy

```python
from Settings.proxy_manger import ProxyManager

async def example(self):
    proxy_manger = ProxyManager(self.api_caller)
    data = await proxy_manger.proxy_controller(
        session=session,
        url=self.book_data.url.get("main_url"),
        method=self.book_data.method,
    )
```