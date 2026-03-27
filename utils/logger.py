import logging

# LOG_LEVEL = logging.INFO
LOG_LEVEL = logging.ERROR


def process_logger(logger, file_name):
    logger.setLevel(LOG_LEVEL)
    # create file handler which logs even debug messages
    fh = logging.FileHandler(file_name + '.log')
    fh.setLevel(LOG_LEVEL)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(LOG_LEVEL)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
