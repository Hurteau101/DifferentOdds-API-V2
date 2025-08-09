from datetime import datetime

class BaseLogger:
    @classmethod
    def format(cls, message, level, **kwargs):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        additional_info = f" | Additional Info: {kwargs}" if kwargs else ""
        return f"{timestamp} - {level.upper()}: {message} {additional_info}"


# Class to log messages to the console
# Example usage:
# ConsoleLogger.log("No Underdog Data Found", level="INFO", "API_DATA = None")
class ConsoleLogger(BaseLogger):
    @classmethod
    def log(cls, message, level="info", **kwargs):
        formatted_message = cls.format(message, level, **kwargs)
        print(formatted_message)


# Class to log messages to a file
# Example usage:
# Option 1: Use default log file "app.log"
# FileLogger.log("This is a file log message", level="WARNING", action="write")

# Option 2: Set a custom log file, then log
# FileLogger.set_log_file("custom_log.txt")
# FileLogger.log("Logging to a custom file", level="ERROR", error_code=500)
class FileLogger(BaseLogger):
    def __init__(self, path="app.log"):
        self.log_file = path

    def set_log_file(self, path):
        self.log_file = path

    def log(self, message, level="info", **kwargs):
        formatted_message = self.format(message, level, **kwargs)
        with open(self.log_file, "a") as file:
            file.write(formatted_message + " \n")