from utils.logger import process_logger, logging

override_keyword = "override"

logger = logging.getLogger('key_matching')
process_logger(logger, file_name='key_matching')

key_mapping_folder = 'key_mapping'
fields_mapping_folder = 'fields_mapping'
output_pdf_folder = "output"
forms_folder = "forms"

keys_extension = ".keys"
pdf_extension = ".pdf"
fields_extension = ".fields"
log_extension = ".log"
json_extension = ".json"

ANNOT_KEY = '/Annots'
ANNOT_FIELD_KEY = '/T'
ANNOT_FIELD_TYPE_KEY = '/FT'
ANNOT_FIELD_TYPE_TXT = '/Tx'
ANNOT_FIELD_TYPE_BTN = '/Btn'
ANNOT_VAL_KEY = '/V'
ANNOT_RECT_KEY = '/Rect'
SUBTYPE_KEY = '/Subtype'
WIDGET_SUBTYPE_KEY = '/Widget'
