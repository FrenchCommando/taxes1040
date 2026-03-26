# TODO

## Refactor: static `.fields` files

Replace `fill_fields_files()` (~850 lines of `f.write()` calls) with static `.fields` files committed to the repo.

### Steps
1. Generate the `.fields` files by running the current pipeline
2. Commit the `.fields` files under `fields_mapping/{year}/`
3. Delete `create_empty_fields()` and `fill_fields_files()` from `fill_keys.py`
4. Update `fill_keys.main()` — remove calls to those two functions, keep `generate_keys_pdf()` and `move_keys_to_parent()`
5. Update `clean()` in `utils/forms_clean.py` — stop deleting `fields_mapping/`
6. Note: `clean()` also does `remove_by_extension(keys_extension)` which walks the entire cwd and deletes all `.keys` files including the rewritten ones in `forms/` — fine since they're regenerated each run

### Benefits
- Easier to edit (text files instead of Python `f.write()` statements)
- Diffable in git (see exactly what changed between years)
- Less code (~850 lines removed)
- Less error-prone (no risk of Python typo breaking field order)
