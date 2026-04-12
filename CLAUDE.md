# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Python tool that computes and fills IRS Form 1040 and related federal/state tax forms (2018-2025). 
It reads financial input data (W2, 1099, 1098), performs tax computations, and outputs filled PDF forms plus JSON summaries.

Inputs: the initial version was parsing raw `pdf`/`xml`/`csv` files - a lot of wasted energy - now inputs are `json` filled by the user

Outputs: initially focused on the `pdf` itself (and focusing on printing `pdf` with annotations) - now `json` is more readable and useful (shows clearly what numbers to write on the actual form + summary of important figures)

## How to Run

```bash
# Activate virtualenv
source venv/Scripts/activate   # Windows/Git Bash

# Install dependencies
pip install -r requirements.txt

# Run full pipeline (computation + PDF output)
python main.py

# Dev mode: set dev_mode = True in main.py to regenerate .keys from .fields

# Compute marginal tax rates
python marginal_rates.py                  # default: $100 delta, 2025
python marginal_rates.py --delta 10000    # larger delta for more precision
python marginal_rates.py --year 2024      # different year

# Run tests
python -m unittest tests.test_computation -v

# Regenerate test expected outputs after computation changes
python tests/generate_scenarios_2025.py
```

The entry point is `main.py` with two modes:
- **Default** (`dev_mode = False`) - runs `fill_taxes.main()` and `make_pdf_output.main()` (tax computation, PDF filling, JSON output)
- **Dev mode** (`dev_mode = True`) - first regenerates `.keys` files from `.fields` mappings for each year in `all_years`, cleans up intermediate artifacts (`key_mapping/` folder and debug PDFs), then runs the full pipeline (same as default mode). Use when adding a new form PDF, editing a `.fields` file, or adding a new tax year.

### Dev mode pipeline
1. **Key matching** (`pipeline/key_matcher.py`) - opens each blank IRS PDF, iterates over annotation widgets, and produces raw `.keys` files in `key_mapping/` mapping each annotation name to a sequential integer index and its type (`/Tx` text or `/Btn` checkbox). Also generates debug PDFs with integers filled in so you can visually identify which index corresponds to which box.
2. **Field filling** (`pipeline/fill_keys.py`) - reads the static `.fields` files from `fields_mapping/{year}/` and rewrites the `.keys` files, replacing integer indices with human-readable names:
   - `.fields` files are committed to the repo and edited directly. Each line is a positional format: a single word (e.g. `single`) names the next annotation; a multi-word line (e.g. `self first_name_initial last_name ssn`) names the next N annotations with `prefix_suffix` keys
   - `build_keys()` walks the `.fields` file and original `.keys` file in parallel via an iterator, producing a new `.keys` file where the integer index column is replaced by the human-readable name
   - `generate_keys_pdf()` produces debug PDFs in `fields_mapping/{year}/` with human-readable names overlaid for visual verification (gitignored)
   - `move_keys_to_parent()` moves the rewritten `.keys` files into `forms/{year}/` alongside the PDFs, where they are consumed at tax-fill time

### Tax computation (`pipeline/fill_taxes.py`)
Reads input data, computes taxes, outputs JSON to `output/{year}/`.

### PDF output (`pipeline/make_pdf_output.py`)
Reads `output/{year}/data.json`, fills blank PDFs using `.keys` mappings, merges into `output/{year}/forms.pdf`. Logs errors for computation keys that don't match any `.keys` entry (detects field name mismatches between computation and PDF layout).

The `all_years` list in `main.py` controls which years are processed - dev mode (key regeneration), tax computation (`fill_taxes`), and PDF output (`make_pdf_output`) all receive this same list.

## Project Structure

```
taxes1040/
|-- main.py                     # entry point
|-- marginal_rates.py           # marginal tax rate analysis (standalone)
|-- pipeline/                   # pipeline scripts
|   |-- fill_keys.py            # .fields -> .keys rewriting
|   |-- fill_taxes.py           # tax computation orchestration + JSON output
|   |-- key_matcher.py          # PDF annotation -> raw .keys extraction
|   +-- make_pdf_output.py      # .keys + data.json -> filled PDFs
|-- computation/                # tax logic
|   |-- legacy/                 # frozen monoliths (2018-2023), one per year
|   |-- forms_core_2024.py      # thin config wrapper -> forms_core_impl
|   |-- forms_core_2025.py      # thin config wrapper -> forms_core_impl (with field_maps)
|   |-- forms_core_impl.py      # shared computation engine for 2024+
|   |-- forms_functions.py      # tax bracket functions + get_main_info
|   +-- form_worksheet_names.py # form key constants (k_1040, k_6251, etc.)
|-- utils/                      # infrastructure
|   |-- forms_constants.py      # PDF annotation constants, folder/extension names
|   |-- forms_utils.py          # PDF read/write via pdfrw, key file loading
|   +-- logger.py               # root logger configuration (single file: logs/taxes1040.log)
|-- tests/                      # test suite
|   |-- test_computation.py     # scenario-based tests (discovers scenarios/<year>/) + real data test
|   |-- generate_scenarios_2025.py  # generates/regenerates 2025 expected outputs
|   +-- scenarios/              # scenarios organized by year
|       +-- 2025/               # each scenario has input.json + expected JSONs
|-- forms/                      # blank PDFs + committed .keys files, by year
|-- fields_mapping/             # .fields files (positional annotation mappings), by year
|-- input_data/                 # input JSON, by year
|-- output/{year}/              # all generated output per year
|   |-- data.json               # all computed form field values (tracked)
|   |-- summary.json            # human-readable key results (tracked)
|   |-- worksheet.json          # intermediate worksheet computations (tracked)
|   |-- carryover.json          # values passed to next year (tracked)
|   |-- marginal_rates.json     # marginal tax rates by income category (tracked)
|   |-- forms.pdf               # merged PDF (gitignored)
|   +-- Federal/, ny/           # individual filled PDFs (gitignored)
+-- logs/                       # log files (gitignored)
```

## Architecture

**Pipeline flow:** `forms/{year}/` (blank PDFs) -> `key_mapping/` (raw `.keys` with integer indices) -> `fields_mapping/{year}/` (static `.fields` files rewrite `.keys` with human-readable names) -> rewritten `.keys` committed in `forms/{year}/` -> `output/{year}/` (filled PDFs + JSON)

**PDF generation happens at three stages:**
1. **Debug PDF (integer indices)** - `key_matcher.py` fills each blank PDF with sequential integers and writes it to `key_mapping/{year}/`. Used to visually identify which integer index maps to which box on the form. Gitignored.
2. **Debug PDF (human-readable names)** - `fill_keys.py:process_fields()` loads the original keys (integers), overlays the rewritten keys (human-readable names), checks all `/Btn` checkboxes, and writes a PDF to `fields_mapping/{year}/`. Used to verify the `.fields` positional mapping is correct. Gitignored.
3. **Final output PDFs** - `make_pdf_output.py:fill_pdfs()` reads the rewritten `.keys` from `forms/{year}/`, joins `annotation_name -> human_readable_name` with `forms_state[human_readable_name] -> computed_value`, and fills the blank PDF. Forms with list contents (e.g. multiple 8949 pages) produce suffixed copies (`_0`, `_1`). Then `merge_pdfs()` concatenates all individual PDFs into `output/{year}/forms.pdf`.

**Marginal rate analysis (`marginal_rates.py`):** Standalone script that computes marginal tax rates by finite difference. For each input category (W2 wages, short/long-term capital gains, dividends, interest, 1256 contracts, charitable contributions), it perturbs the input by a configurable delta, re-runs `fill_taxes`, and measures the change in federal, NY state, and NYC tax. Outputs to `output/{year}/marginal_rates.json`. Runs independently of the main pipeline — does not load prior-year carryover.

**Core computation:** Each tax year has its own `computation/forms_core_{year}.py` containing a single `fill_taxes_{year}(d)` function. Old years (2018-2023) are frozen monoliths in `computation/legacy/` - large single functions that compute every form line by line. Years 2024+ use thin config wrappers that call `computation/forms_core_impl.py` - the shared implementation - with a `CONFIG_{year}` dict specifying year-specific constants (standard deduction, AMT thresholds, bracket functions, etc.). All years use an inner `Form` class to accumulate field values into `forms_state` dict. Prior year output can be passed in for carryover values (e.g., capital loss carryover).

**Field mapping layer:** The shared computation (`forms_core_impl.py`) uses 2024 as the canonical year for field names. When PDF forms change layout between years (e.g., f1040 line 11 became 11a in 2025), the year config includes a `field_maps` dict that translates canonical names to the year's actual field names. The mapping is applied as a bulk rename after all computation is done (so cross-form reads during computation use consistent 2024 names). Only forms that changed need mapping entries; stable forms pass through untouched. See `CONFIG_2025` in `forms_core_2025.py` for an example. A `None` value in the mapping means the field was removed.

**Logging:** Configured once in `utils/logger.py` (root logger -> `logs/taxes1040.log`). Each module/function uses `logging.getLogger('descriptive_name')` - the logger name in the output identifies the source (e.g., `key_mapping`, `fields_mapping`, `output_pdf`, `computation`, `fill_pdf`, `load_keys`, `map_folders`).

## Adding a New Tax Year

### Phase 1: Computation

1. **Create the config wrapper** - `computation/forms_core_{year}.py`. Define `CONFIG_{year}` with updated constants (standard deduction, AMT thresholds, bracket limits, etc.) and a one-liner `fill_taxes_{year}(d)` that calls `forms_core_impl.fill_taxes(d, config=CONFIG_{year})`. Use `forms_core_2025.py` as a template.
2. **Update bracket functions** - if tax brackets changed, add `computation_{year}`, `computation_{year}_ny`, etc. to `computation/forms_functions.py`.
3. **Register the year in the pipeline** - add the new fill function to `FILL_FUNCTIONS` in `pipeline/fill_taxes.py` and import it. Add the year string to `all_years` in `main.py`.

### Phase 2: PDF Forms and Field Mapping

4. **Place blank IRS PDFs** in `forms/{year}/Federal/` (and `forms/{year}/ny/` for NY state forms).
5. **Create `.fields` files** in `fields_mapping/{year}/` for each form. Copy from the previous year and adjust for any layout changes. Each `.fields` file is positional - it maps PDF annotation widgets to human-readable field names (see existing files for the format).
6. **Run dev mode** - set `dev_mode = True` in `main.py` and run `python main.py`. This runs `key_matcher` (extracts raw `.keys` from PDFs) then `fill_keys` (rewrites `.keys` using `.fields`). Check the debug PDFs generated in `fields_mapping/{year}/` to verify field names land on the correct boxes.
7. **Add field maps if PDF layout changed** - compare the new year's `.keys` against the previous year's. Any computation field names that changed need a `field_maps` entry in the config. The computation uses 2024 as canonical field names; the mapping translates them after computation. Use `None` to drop a removed field. Only include fields that actually changed.

### Phase 3: Input Data and Validation

8. **Create input data** - `input_data/{year}/input.json` with that year's W2, 1099, 1098, etc.
9. **Run the full pipeline** - set `dev_mode = False` and run `python main.py`. This runs computation (`fill_taxes`) then PDF output (`make_pdf_output`).
10. **Check for field mismatches** - look for `output_pdf` ERROR logs in `logs/taxes1040.log`. These indicate computation keys not found in the `.keys` file, meaning either a missing `field_maps` entry or a new field needing computation logic in `forms_core_impl.py`.
11. **Inspect output** - review `output/{year}/data.json` (all form fields), `summary.json` (key figures), `worksheet.json` (intermediate calculations), and `carryover.json` (values for next year). Open `output/{year}/forms.pdf` and verify values appear in the correct boxes.

### Phase 4: Tests

12. **Create a year-specific scenario generator** - copy `tests/generate_scenarios_2025.py` to `tests/generate_scenarios_{year}.py`, update the import and `SCENARIOS_DIR` path. Scenarios live in `tests/scenarios/{year}/`.
13. **Regenerate test scenarios** - run `python tests/generate_scenarios_{year}.py` to generate expected outputs. The test runner auto-discovers year subfolders.
14. **Run tests** - `python -m unittest tests.test_computation -v` to verify all scenarios pass.
15. **Add new scenarios** if the year introduced new logic paths - add entries to `SCENARIOS` in the year's generator, regenerate, and re-run.

### Notes

- Add form name constants to `computation/form_worksheet_names.py` only if new forms are needed.
- The `trades_per_page_limit` config parameter controls how many trades fit per f8949 page (changed from 14 to 11 in 2025). Check the new year's PDF and update if needed.

## Important Caveats

- Tax tables (for taxable income under ~$100k) are not parsed; bracket-based computation is used instead
- Currently configured for **single filer, no dependents, resident**
- NY IT-196 (itemized deductions) has `.fields`/`.keys` mappings and PDF filling for 2024-2025. Other NY forms (IT-201, IT-2) are "enhanced" PDFs that can't be filled directly; the code computes NY values for JSON output only
- Intermediate artifacts are gitignored: `key_mapping/` (raw `.keys` with integer indices, regenerated from blank PDFs each dev run) and debug PDFs in `fields_mapping/`. The final `.keys` with human-readable names live in `forms/{year}/` and are committed.
- The field mapping layer only handles renamed fields. New fields requiring new computation logic need code additions to `forms_core_impl.py`.
- Form 6251: Part I line 2a (SALT add-back when itemizing) is implemented. Lines 2b-2t (other AMT preference items like depreciation, ISO, passive activities) are not yet implemented. Part II handles exemption phaseout and Part III applies preferential capital gain rates when qualified dividends or Schedule D gains are present. The ShouldFill6251Worksheet screens whether Form 6251 is needed.
- NY IT-196 line 46/47: implements Worksheets 3 and 4 (itemized deduction adjustment for NYAGI $100k-$1M) and the high-income rules (50% of AGI for NYAGI $1M-$10M, 25% for >$10M). The `ny_itemized_deduction_threshold` config controls the line 40/41 overall limit threshold.
- Form 6781: supports both `Contract1256` (individual contracts) and `Realized1256`/`Unrealized1256` (aggregate broker amounts) in 1099 input. The 40/60 split (lines 8/9) flows directly to Schedule D lines 4 (short-term) and 11 (long-term), bypassing Form 8949. When only 1256 contracts exist (no regular trades), Form 8949 is omitted.
- 1099 input: `InterestBondsObligations` (US government bond interest) flows to federal Schedule B and is subtracted on NY IT-201 line 28. `Interest` and `InterestBondsObligations` are separate amounts (Box 1 and Box 3 on 1099-INT).
- Charitable contributions: Schedule A line 11 (cash) is implemented, sourced from the `Charitable` list in input JSON (each entry has `Entity` and `Amount`). Lines 12 (other than cash) and 13 (carryover) are not filled but are included in the line 14 sum. NY IT-196 line 16 mirrors federal line 11.
- Form 1116: computes the foreign tax credit limitation for passive category income. Foreign source income is identified from 1099 entries that have `Foreign Tax Paid`. The limitation fraction (foreign source taxable / worldwide taxable) caps the credit; excess carries forward (saved in `carryover.json`). Schedule B (Form 1116) for carryover tracking and the qualified dividend adjustment (0.5405 multiplier) are not implemented. The adjustment exception applies when foreign source qualified dividends + net capital gain < $20,000 and QDCG worksheet line 5 ≤ $197,300.
- Form 8960: computes Net Investment Income Tax (NIIT) at 3.8% on the lesser of net investment income (interest + dividends + capital gains) or MAGI - $200k (single). Flows to Schedule 2 line 12. Skipped when NIIT is zero. The $200k threshold is not inflation-indexed. Passive activity income, annuities, and Part II deductions (9b state tax allocation, 9c misc expenses) are not implemented.
- `make_pdf_output` filters out `custom_missing_*` keys from `data.json` with a warning log before PDF filling. These are computation-only flags (e.g. Form 1116 income category checkbox) that have no corresponding `.keys` entry.
- `make_pdf_output` logs an error and skips when a computed form has no .keys file, rather than crashing.
