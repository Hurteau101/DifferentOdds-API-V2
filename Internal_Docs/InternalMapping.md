# Internal Mapping Breakdown

## Files

### `ai_mapper.py`
- This uses the OpenAI API to map names. Once names are mapped, 
they are stored in a database for final verification. 
- This is manually run. 


### `find_mapper.py`
- This system first uses RapidFuzz to attempt to map names. If the match fails, the 
unmatched entry is stored in a database, which `ai_mapper.py` later processes. 
If RapidFuzz successfully finds a match, the mapped data is returned and also stored in 
the database to continuously expand and improve the mapping system.

