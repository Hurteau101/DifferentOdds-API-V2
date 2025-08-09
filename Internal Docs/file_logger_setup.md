# Creating DFS Class with Inheritance

This document demonstrates how to set up the FileLogger. 
By default all base sportsbook classes have a file logger set up. 
This is more to demonstrate on how to set up the FileLogger in a separate file

---

### Setting up FileLogger
##### It's best to put this in the __init__ for when you set up the logger.

```python
from Settings.logger import FileLogger
import os
import inspect

class Example:
    def __init__(self):
        self.file_logger = FileLogger()

        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(current_dir, "FileName.log")

        self.file_logger.set_log_file(log_path)
        caller_file_full = inspect.stack()[2].filename  # Path of the caller.
        self.caller_file_name = os.path.basename(caller_file_full) # File name of the caller
    
    # This just shows an example of how to implement
    # This will create the log file in the current directory of the file
    def example_function(self):
        self.file_logger.log(
            message=f"Example Message",
            file=self.caller_file_name, # This shows the file caller [OPTIONAL]
            level="INFO"
        )

```
