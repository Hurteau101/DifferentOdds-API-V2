# Settings Breakdown

## Folders
### `Models`
- This is where all the models (dataclasses) are stored. This keeps all sportsbooks returned data structured as 
they must follow the dataclass structure.
- Each book type is stored in a separate folder.

### `Providers`
- This is where all the providers are stored.
- A provider is a class that stores all the information about a specific book. 
- Such as:
  - Name of Book
  - Urls
  - Method
  - If its active or not.
- This is primarly used for each book but the API also uses this to listen all 
available books and which are active or not.
- Each book type is stored in a separate folder.

---

## Files
## `book_configuration.py`
- This file is more like a helper file that will grab all the providers/book information. 
