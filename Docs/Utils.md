# Utils Breakdown

## Files

### `helpers.py`
- This file contains helper functions that are used throughout the project.

### `proxy_manager.py`
- This file contains the proxy manager class.
- This class is used to manage the proxies and API calls with them.
- You will use this file/class when you need to use proxies for API calls.

### `request_caller.py`
- This file contains the request caller class.
- This class is used to make API calls.
- It will allow you to make Async calls or Spoofed Sync calls. This is decided via the `SportbookRequestType` enum, 
which all sportsbooks in this project will use. This determines whether the call is Async or Spoofed.
- You can also pass in valid status codes via `valid_status_codes` which will be used when the request is made.
If the status code is not in this list, the `_capture_error` function will be called, which will be a sentry error. (Reference `Monitoring.md`)
