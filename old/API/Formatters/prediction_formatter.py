class BaseFormatter:
    """Base formatter that returns data as-is."""
    def format(self, data):
        return data

class GameFormatter(BaseFormatter):
    def format(self, data):
        return data

def get_prediction_formatter(format_name, redis_data):
    mapping = {
        "base": BaseFormatter,
        "game": GameFormatter,
    }

    formatter = mapping[format_name]()
    return formatter.format(redis_data)