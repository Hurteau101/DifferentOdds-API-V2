# Database Breakdown

**Quick Overview:**
- In this application majority of data is stored in Redis. 
We utilize a database more for storing any internal mapping and API keys. 
Anything that is long-lasting and doesn't refresh often.

---

## Files

### `database.py`
- This contains all functions that interact with the database. 

### `table_creation.py`
- This contains all functions that create tables in the database.
