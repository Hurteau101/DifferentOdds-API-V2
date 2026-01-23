# Directory Breakdown

# Authentication
### `Books`
- This will contain all the books that require authentication.

---
# Books
**** WIP ****

----
# Monitoring
- This is the entry point for Sentry monitoring. Along with any helper methods.
---

# Redis
### `certs`
- This is where the redis ca.crt lives.
- `redis_manager.py` handles all redis connections and interactions (connection pooling).

---

# Settings
### `Providers`
- This is where all the books external API information lives. [Title, Name, URL, Method, Headers, is_active]

### `book_configuration.py`
- This configuration allows you to connect to the specific section of a provider. Example: DFS Provider or Prediction Provider

### `Models`
- This contains all the Pydantic models for each type of book. Example: DFS or Prediction.

---

# Utils
### `request_caller.py`
- This is a helper function to make external API calls. Supports regular Async Calls or Spoofed Async calls.
- Handles response validation.
### `clean_data.py`
- Helper functions, to clean data.

---
# Mapping
