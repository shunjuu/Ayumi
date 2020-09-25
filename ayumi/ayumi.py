# Handles all aspects of logging

import logging

from collections import defaultdict
from dynaconf import settings
from getpass import getuser
from inspect import stack, getmodule, currentframe
from json import dumps
from os.path import basename
from socket import getfqdn
from time import time
from typing import Dict, Tuple

_SETTINGS_PREFIX = "AYUMI_"

_EXCHANGE = "logs-gateway"
_CONSOLE_FORMAT = "[{filename}:{functionname}]: {msg}"
_DATE_FORMAT = "%a|%b%y|%X|%Z"
_LOG_FORMAT = "[%(asctime)s][%(levelname)s]: %(message)s"
_LOG_LEVEL = "NOTSET"

# Try loading from Dynaconf 3.1.1, and the legacy Dynaconf afterwards
try:
    from config import settings
    _EXCHANGE = settings.get(_SETTINGS_PREFIX + "EXCHANGE", _EXCHANGE)
    _CONSOLE_FORMAT = settings.get(_SETTINGS_PREFIX + "CONSOLE_FORMAT", _CONSOLE_FORMAT)
    _DATE_FORMAT = settings.get(_SETTINGS_PREFIX + "DATE_FORMAT", _DATE_FORMAT)
    _LOG_FORMAT = settings.get(_SETTINGS_PREFIX + "LOG_FORMAT", _LOG_FORMAT)
    _LOG_LEVEL = settings.get(_SETTINGS_PREFIX + "LOG_LEVEL", _LOG_LEVEL)
except ImportError:
    try:
        from dynaconf import settings
        _EXCHANGE = settings.get(_SETTINGS_PREFIX + "EXCHANGE", _EXCHANGE)
        _CONSOLE_FORMAT = settings.get(_SETTINGS_PREFIX + "CONSOLE_FORMAT", _CONSOLE_FORMAT)
        _DATE_FORMAT = settings.get(_SETTINGS_PREFIX + "DATE_FORMAT", _DATE_FORMAT)
        _LOG_FORMAT = settings.get(_SETTINGS_PREFIX + "LOG_FORMAT", _LOG_FORMAT)
        _LOG_LEVEL = settings.get(_SETTINGS_PREFIX + "LOG_LEVEL", _LOG_LEVEL)
    except ImportError:
        pass

try:
    import pika
    _PIKA_IMPORTED = True
except ImportError:
    _PIKA_IMPORTED = False

try:
    import rabbitpy
    _RABBITPY_IMPORTED = True
except ImportError:
    _RABBITPY_IMPORTED = False

class Ayumi():

    pika_channel = None
    rabbitpy_channel = None

    logging.basicConfig(format=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    logger = logging.getLogger() # Use root logger so all other apps can output too.
    logger.setLevel(logging.getLevelName(_LOG_LEVEL.upper()))


    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'

    LRED = '\033[91m'
    LGREEN = '\033[92m'
    LYELLOW = '\033[93m'
    LBLUE = '\033[94m'
    LMAGENTA = '\033[95m'
    LCYAN = '\033[96m'

    _ENDC = '\033[0m'


    @classmethod
    def get_logger(cls) -> logging.Logger:
        return cls.logger

    @classmethod
    def set_pika_channel(cls, channel) -> None:
        cls.pika_channel = channel

    @classmethod
    def set_rabbitpy_channel(cls, channel) -> None:
        cls.rabbitpy_channel = channel

    @classmethod
    def notset(cls, msg: str, color: str = "") -> None:
        cls._console(msg, color)
        cls._publish(msg, color)

    @classmethod
    def debug(cls, msg: str, color: str = "") -> None:
        cls._console(msg, color)
        cls._publish(msg, color)

    @classmethod
    def info(cls, msg: str, color: str = "") -> None:
        cls._console(msg, color)
        cls._publish(msg, color)

    @classmethod
    def warning(cls, msg: str, color: str = "") -> None:
        cls._console(msg, color)
        cls._publish(msg, color)

    @classmethod
    def critical(cls, msg: str, color: str = "") -> None:
        cls._console(msg, color)
        cls._publish(msg, color)

    @classmethod
    def error(cls, msg: str, color: str = "") -> None:
        cls._console(msg, color)
        cls._publish(msg, color)

    """
    --- ACTUAL FUNCTIONS FOR LOGGING/PUBLISHING/ETC ---
    """

    @classmethod
    def _console(cls, msg: str, color: str) -> None:
        filename, functionname = Ayumi.get_calling_details()
        getattr(cls.logger, currentframe().f_back.f_code.co_name)("{}{}{}".format(
            color,
            _CONSOLE_FORMAT.format(
                filename=filename, functionname=functionname, msg=msg
            ),
            cls._ENDC
        ))

    @classmethod
    def _publish(cls, msg: str, color: str) -> None:

        # Color can be an empty string, so convert that to None for JSON.
        if not color:
            color = None

        # Publish to Pika
        if _PIKA_IMPORTED and cls.pika_channel:
            cls.pika_channel.basic_publish(
                body=dumps({"body": msg, "color": color}),
                exchange=_EXCHANGE,
                routing_key=currentframe().f_back.f_code.co_name.lower(),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                    headers=Ayumi.get_headers(),
                    timestamp=int(time())
                )
            )

        # Publish to RabbitPy
        if _RABBITPY_IMPORTED and cls.rabbitpy_channel:
            message = rabbitpy.Message(
                cls.rabbitpy_channel,
                dumps({"body": msg, "color": color}),
                properties={
                    "content_type": "application/json",
                    "delivery_mode": 2,
                    "headers": Ayumi.get_headers(),
                    "timestamp": int(time())
                })
            message.publish(_EXCHANGE, currentframe().f_back.f_code.co_name.lower())

    @staticmethod
    def get_headers() -> Dict[str, str]:
        return {
            "user": getuser(),
            "host": getfqdn(),
        }

    @staticmethod
    def get_calling_details(level: int = 3) -> Tuple[str, str]:
        """Gets the name of the file that called a logging function for logging output"""
        # Set to 2, because it's a second level up calling trace
        frame = stack()[level]
        # The third object in the tuple is the function name
        functionname = str(frame[3])
        module = getmodule(frame[0])
        filename = Ayumi.get_base_filename(module.__file__)
        return (filename, functionname)

    @staticmethod
    def get_base_filename(filename: str) -> str:
        """Gets the basename of the filename, used for logging purposes"""
        return basename(filename)
