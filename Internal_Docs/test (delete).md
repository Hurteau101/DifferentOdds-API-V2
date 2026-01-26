# PyCharm + pytest: Running One Book vs All Books (Mapper/Auth Tests)

## Why this works
Our parametrized tests use `ids=...` so each case includes the book name in the test ID.

Example:

This produces test names like:
- `test_auths[betmgm]`
- `test_auths[caesars]`

Because the book name appears in the test name, pytest can filter by it.

---

## Two PyCharm Run Configurations (recommended)

### 1) **All Books**
- **Configuration type:** pytest
- **Target:** the test file (e.g. `Tests/Mapper/mapper_tests.py` or `Tests/Auths/auth_tests.py`)
- **Additional Arguments:** *(empty)*

Result: runs all parametrized cases (all books).

---

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

---

## Notes / Tips
- `-k` is a substring match filter applied to the test node id.
- If you remove `-k ...`, pytest runs everything.
- You can switch the book by changing `betmgm` to any other book name in `TEST_AUTH_MAPPINGS`.
- You can also filter by just the book name:
  ```text
  -k "betmgm"
  ```
  but including the test function name makes it less likely to match unrelated tests.

---


- Run 2 books -k "test_auths and (betmgm or caesars)"