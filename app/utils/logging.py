import logging

_logger = None

def get_logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger("youtube_cache")
        _logger.setLevel(logging.INFO)
        if not _logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            _logger.addHandler(handler)
    return _logger