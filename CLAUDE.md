# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Python tool that computes and fills IRS Form 1040 and related federal/state tax forms (2018–2024). 
It reads financial input data (W2, 1099, 1098), performs tax computations, and outputs filled PDF forms plus JSON summaries.

Inputs: the initial version was parsing raw `pdf`/`xml`/`csv` files - a lot of wasted energy - now inputs are `json` filled by the user

Outputs: initially focused on the `pdf` itself (and focusing on printing `pdf` with annotations) - now `json` is more readable and useful (shows clearly what numbers to write on the actual form + summary of important figures)

## How to Run

```bash
# Activate virtualenv
source venv/Scripts/activate   # Windows/Git Bash

# Install dependencies
pip install -r requirements.txt

# Run the full pipeline
python main.py
```

The entry point is `main.py`. It runs three stages:
1. **Key matching** (`key_matcher.py`) — extracts PDF annotation field names from blank IRS forms, generates `.keys` mapping files
2. **Field filling** (`fill_keys.py`) — first creates empty `.fields` files for every `.keys` file (via `create_empty_fields()`, using exclusive-create mode `'x'` to skip existing files), then `fill_fields_files()` overwrites the known ones with actual human-readable field definitions. This ensures every form has a `.fields` file even if `fill_fields_files()` doesn't handle it yet.
3. **Tax computation** (`fill_taxes.py`) — reads input data, computes taxes, fills PDFs, outputs JSON

Edit `main.py` to select which tax years to process. Edit `fill_taxes.py:main()` to control which year computations run (uncomment/comment year blocks).

## Architecture

**Pipeline flow:** `forms/{year}/` (blank PDFs) → `key_mapping/` → `fields_mapping/` → `output/{year}/` (filled PDFs)

**Core computation:** Each tax year has its own `utils/forms_core_{year}.py` containing a single `fill_taxes_{year}(d, output_prev=None)` function. These are large monolithic functions (~1500+ lines) that compute every form line by line. They use an inner `Form` class to accumulate field values into `forms_state` dict. Prior year output can be passed in for carryover values (e.g., capital loss carryover).

**Key files:**
- `utils/forms_functions.py` — shared computation helpers (tax bracket calculations per year, `get_main_info`)
- `utils/forms_constants.py` — PDF annotation constants, folder/extension names, logger setup
- `utils/forms_utils.py` — PDF read/write via `pdfrw`, key file loading
- `utils/form_worksheet_names.py` — string constants for form keys (e.g., `k_1040 = 'Federal/f1040'`) and worksheet names
- `input_data/build_json.py` + `input_data/parse_data.py` — parse W2/1099 source documents into `input.json`

**Input:** `input_data/{year}/input.json` — JSON with W2, 1099, 1098 data. Additional personal info (filing status, address, etc.) is hardcoded in `fill_taxes.py:gather_inputs()`.

**Output:**
- `output/{year}/Federal/` — filled PDF forms
- `data{year}.json` — all computed form field values
- `summary{year}.json` — human-readable key results
- `worksheet{year}.json` — intermediate worksheet computations
- `forms{year}.pdf` — merged PDF (note: merged PDFs lose annotations; individual PDFs are more reliable)

## Adding a New Tax Year

1. Copy the latest `utils/forms_core_{year}.py`, update tax brackets/thresholds/form changes
2. Add the corresponding computation function to `utils/forms_functions.py` if bracket tables changed
3. Place blank IRS PDF forms in `forms/{year}/Federal/` (and `forms/{year}/ny/` for NY)
4. Create `input_data/{year}/input.json` with that year's financial data
5. Add the new year to `main.py` loop and uncomment in `fill_taxes.py:main()`
6. Add form name constants to `utils/form_worksheet_names.py` if new forms are needed

## Important Caveats

- Tax tables (for taxable income under ~$100k) are not parsed; bracket-based computation is used instead
- Currently configured for **single filer, no dependents, resident**
- NY state forms are "enhanced" and can't be filled directly; the code computes NY values for JSON output only
- The `clean()` step in `utils/forms_clean.py` removes intermediate `.keys` files and mapping folders after processing
