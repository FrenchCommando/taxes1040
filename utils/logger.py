import logging
import os

LOG_LEVEL = logging.INFO

logs_folder = "logs"
os.makedirs(logs_folder, exist_ok=True)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

fh = logging.FileHandler(os.path.join(logs_folder, 'taxes1040.log'))
fh.setLevel(LOG_LEVEL)
fh.setFormatter(formatter)

ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)
ch.setFormatter(formatter)

root = logging.getLogger()
root.setLevel(LOG_LEVEL)
root.addHandler(fh)
root.addHandler(ch)
