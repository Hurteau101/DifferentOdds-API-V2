from datetime import timedelta
from enum import StrEnum
from sqlalchemy.orm import sessionmaker
from Database.base_db import sync_engine
from Database.Logging.logging_db import LoggingDetails
from loguru import logger
from LoggingHelper.discord_log import send_discord_message
from Utils.helpers import is_production


class ErrorTypes(StrEnum):
    AUTH = "Authentication Error"
    MAPPING = "Mapping Error"
    API_NO_DATA = "API Response Error"
    NO_EXTRACTION_DATA = "Extraction Error"
    ESPN_NO_DATA = "ESPN API Response Error"
    MISC = "Misc Error"

def production_log(book_name: str, error_type: ErrorTypes, error_message: str):
    if not all([book_name, error_type, error_message]):
        logger.error("Missing required parameters")
        return

    if not isinstance(error_type, ErrorTypes):
        logger.error("error_type must be an instance of ErrorTypes")
        return

    session = sessionmaker(bind=sync_engine())

    with session() as db_session:
        log_details = LoggingDetails.update_error(db_session, {"book": book_name, "error_type": error_type.value, "message": error_message})

        if not log_details:
            logger.error("Failed to insert log - No log details returned")
            return

        log_id, last_sent, last_occurrence, count = log_details.log_id, log_details.last_sent, log_details.last_occurrence, log_details.count

        if not all([log_id, last_sent, last_occurrence]):
            none_values = [k for k,v in {"log_id": log_id, "last_sent": last_sent, "last_occurrence": last_occurrence}.items() if v is None]

            logger.error(f"Failed to extract required details from database [${', '.join(none_values)}]")
            return

        time_difference = last_occurrence - last_sent

        if count == 1 or time_difference >= timedelta(hours=1):
            send_discord_message(
                book_name=book_name,
                error_type=error_type,
                error_message=error_message,
                count=count
            )

def env_log(book_name: str, error_type: ErrorTypes, error_message: str):
    logger.error(f"{book_name} - {error_type} - {error_message}")


def insert_log(book_name: str, error_type: ErrorTypes, error_message: str):
    """
    Updates the logging details in the database and sends a message to Discord (Prod) or message log (ENV)
    if the error count is greater than 1 or the last occurrence is more than an hour ago.
    :param book_name: The name of the book that the error occurred in.
    :param error_type: The type of error that occurred.
    :param error_message: The error message.
    """
    is_prod = is_production()
    if is_prod:
        production_log(book_name, error_type, error_message)
    else:
        env_log(book_name, error_type, error_message)
