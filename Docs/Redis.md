# Redis Breakdown

## Files

### `Certs`
- This is where the redis ca.crt lives. This is for the remote redis server.

### `redis_manager.py`
- Handles all redis connections and interactions. Typical through connection pooling.
- All functions that interact with redis should be in this file.
---

## Connecting to Remote Redis
### Setting Up
- Ensure you have the location of the redis ca.crt.
- If you are on windows, its best to use WSL.

### Connecting to Remote Redis Server
```redis-cli \
  -h [Insert Redis IP] \
  -p [Insert Redis Port] \
  --tls \
  --cacert /mnt/c/Users/Devon/OneDrive/Desktop/ca.crt (Example Path) \
  --user [Insert Redis Username] \
  -a [Insert Redis Password]
```