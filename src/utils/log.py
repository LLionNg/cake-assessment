import logging


def setup_logging(level: str) -> None:
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("src").setLevel(level.upper())
