import logging
from utils.logger import process_logger


logger = logging.getLogger('key_matching')
process_logger(logger, file_name='key_matching')

key_mapping_folder = 'key_mapping'
fields_mapping_folder = 'fields_mapping'
utils_folders = ["__", key_mapping_folder, fields_mapping_folder]

keys_extension = ".keys"
pdf_extension = ".pdf"
fields_extension = ".fields"

ANNOT_KEY = '/Annots'
ANNOT_FIELD_KEY = '/T'
ANNOT_FIELD_TYPE_KEY = '/FT'
ANNOT_VAL_KEY = '/V'
ANNOT_RECT_KEY = '/Rect'
SUBTYPE_KEY = '/Subtype'
WIDGET_SUBTYPE_KEY = '/Widget'
