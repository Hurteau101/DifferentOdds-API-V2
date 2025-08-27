import os
from Settings.logger import FileLogger


def create_logging_setup(folder_name, file_name):
    # Logging setup
    API_DIR = os.path.dirname(os.path.abspath(__file__))
    log_directory = os.path.join(API_DIR, "API Logs", folder_name)
    os.makedirs(log_directory, exist_ok=True)
    log_path = os.path.join(log_directory, file_name)
    file_logger = FileLogger(log_path)
    return file_logger
