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
1. **Key matching** (`key_matcher.py`) — opens each blank IRS PDF, iterates over annotation widgets, and produces raw `.keys` files in `key_mapping/` mapping each annotation name to a sequential integer index and its type (`/Tx` text or `/Btn` checkbox). Also generates debug PDFs with integers filled in so you can visually identify which index corresponds to which box.
2. **Field filling** (`fill_keys.py`) — a build-time step that rewrites the `.keys` files, replacing integer indices with human-readable names:
   - `create_empty_fields()` creates a blank `.fields` file for every `.keys` file (exclusive-create mode `'x'` to skip existing)
   - `fill_fields_files()` writes human-readable field definitions into each `.fields` file, form by form. Each line is a positional format: a single word (e.g. `single`) names the next annotation; a multi-word line (e.g. `self first_name_initial last_name ssn`) names the next N annotations with `prefix_suffix` keys
   - `build_keys()` walks the `.fields` file and original `.keys` file in parallel via an iterator, producing a new `.keys` file where the integer index column is replaced by the human-readable name
   - `move_keys_to_parent()` moves the rewritten `.keys` files into `forms/{year}/` alongside the PDFs, where they are consumed at tax-fill time
3. **Tax computation** (`fill_taxes.py`) — reads input data, computes taxes, fills PDFs, outputs JSON. The `fill_pdfs()` function reads the final `.keys` files (`annotation_name → human_readable_name, type`) and joins them with `forms_state` (keyed by human-readable names) to write values into the PDF annotations.

Edit `main.py` to select which tax years to process. Edit `fill_taxes.py:main()` to control which year computations run (uncomment/comment year blocks).

## Architecture

**Pipeline flow:** `forms/{year}/` (blank PDFs) → `key_mapping/` (raw `.keys` with integer indices) → `fields_mapping/` (`.fields` definitions rewrite `.keys` with human-readable names) → rewritten `.keys` moved back to `forms/{year}/` → `output/{year}/` (filled PDFs)

**PDF generation happens at three stages:**
1. **Debug PDF (integer indices)** — `key_matcher.py` fills each blank PDF with sequential integers and writes it to `key_mapping/{year}/`. Used to visually identify which integer index maps to which box on the form.
2. **Debug PDF (human-readable names)** — `fill_keys.py:process_fields()` loads the original keys (integers), overlays the rewritten keys (human-readable names), checks all `/Btn` checkboxes, and writes a PDF to `fields_mapping/{year}/`. Used to verify the `.fields` positional mapping is correct.
3. **Final output PDFs** — `fill_taxes.py:fill_pdfs()` reads the rewritten `.keys` from `forms/{year}/`, joins `annotation_name → human_readable_name` with `forms_state[human_readable_name] → computed_value`, and fills the blank PDF. Forms with list contents (e.g. multiple 8949 pages) produce suffixed copies (`_0`, `_1`). Then `merge_pdfs()` concatenates all individual PDFs into `forms{year}.pdf`.

Debug PDFs from stages 1 and 2 are cleaned up by `utils/forms_clean.py` after processing.

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
