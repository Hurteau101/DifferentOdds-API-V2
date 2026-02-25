# Tests Breakdown


## Folders

### `Auths`
- This contains the file to test all authentications. This will run through all books that require 
authentication and ensure it is running properly.
- All auth books to test live in `common_test_helper.py`. So when removing or adding books, you will modify this file (`TEST_MAPPER_BOOKS`).
- If you don't want to remove a book, but instead want to make it inactive, then you can set `active = False`

### `Mapper`
- This contains the file to test all mapping. This will run through all books that require 
mapping and ensure it is running properly.
- All mapping books to test live in `common_test_helper.py`. So when removing or adding books, you will modify this file (`TEST_AUTH_BOOKS`).
- If you don't want to remove a book, but instead want to make it inactive, then you can set `active = False`

### `Prediction_Liquidity`
- This contains the file to test all Prediction and Liquidity books.
- If you don't want to remove a book, but instead want to make it inactive, then you can set `active = False`
- If you want to store the results from each book that is ran, you will set `save_json = True`

### `SGP`
- This contains the file to test all SGP.
- If you don't want to remove a book, but instead want to make it inactive, then you can set `active = False`
- When adding a book to the `SGP_DATA` list, you need to ensure to put `requires_map` to `True` if this book requires 
pre-authentication before running. Also if the SGP Book requires mapping, you need to insert `mapped_key` 
with the mapping redis key name as the value.
- Also before running, ensure all books that are going to be ran, have valid links inside of `links` list.

### `DFS`
- This contains the file to test all DFS.
- If you don't want to remove a book, but instead want to make it inactive, then you can set `active = False`
- If you want to store the results from each book that is ran, you will set `save_json = True`

### `Sportsbooks`
- This contains the file to test all Sportsbooks.
- If you don't want to remove a book, but instead want to make it inactive, then you can set `active = False`
- If you want to store the results from each book that is ran, you will set `save_json = True`

---

## Files
### `common_test_helper.py`
- This file contains all the books for Auths and Mapping. As well helper functions that are used in some of the tests.

### `conftest.py`
- This file creates asyncio fixtures that are used in the tests. This is mostly used for the Redis connection.

### `pytest.ini`
- This file contains the configuration for the tests.

---

# Running Tests
- All tests will use `ids=lambda` - We use this so each test produces a unique name (ex. `test_auths[betmgm]`, `test_auths[caesar]`). The main reason is to be able to filter out books. 
So we can run multiple test books or a single book.

## Example Cases
### 1) **All Books**
- **Configuration type:** pytest
- **Target:** the test file (e.g. `Tests/Mapper/mapper_tests.py` or `Tests/Auths/auth_tests.py`)
- **Additional Arguments:** *(empty)*

Result: runs all parametrized cases (all books).

### 2) **Single Book (filtered)**
- **Configuration type:** pytest
- **Target:** the same test file
- **Additional Arguments:**
  - Mapper example:
    ```text
    -k "test_mappers and betmgm"
    ```
  - Auth example:
    ```text
    -k "test_auths and betmgm"
    ```

Result: runs only the case whose test name contains both the function name and the book name.

### 3) **Multiple Books**
- **Configuration type:** pytest
- **Target:** the same test file
- **Additional Arguments:**
  - Mapper example:
    ```text
    -k "test_mappers and (fourcx or caesars)"
    ```
  - Auth example:
    ```text
    -k "test_auths and (fourcx or caesars)"
    ```

Result: runs all parametrized cases whose test names match the function name and any of the specified books 
(ex. fourcx or caesars).
