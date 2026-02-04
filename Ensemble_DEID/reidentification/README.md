# Re-identification Module

This folder contains the re-identification functionality, which is **completely separate** from the de-identification pipeline.

## Purpose

Re-identification restores the original text from anonymized output using the metadata generated during de-identification.

## Usage

### Basic Usage (Single Page)

From the project root directory:

```bash
python reidentification/reidentify.py
```

This will:
- **Read from** `output/ensemble_metadata.json` (metadata from de-identification)
- **Read from** `output/anonymized_output.txt` (anonymized text)
- **Write to** `reidentification/output/{doc_id}_page_{page_number}_reidentified.txt` (restored original text, one per page)
- **Write to** `reidentification/output/reid_map_{doc_id}.json` (document-level re-identification mapping, supports multi-page)

**Output Structure**:
- Re-identified text files are generated per page: `{doc_id}_page_{page_number}_reidentified.txt`
- Re-ID map is document-level (constant per document): `reid_map_{doc_id}.json`
- The re-ID map contains a `pages` dictionary with all pages, making it flexible for multi-page documents

### Custom Paths

You can specify custom paths:

```bash
python reidentification/reidentify.py \
    --metadata output/ensemble_metadata.json \
    --anonymized output/anonymized_output.txt \
    --page 1 \
    --output reidentification/output/custom_reidentified.txt \
    --reid-map-output reidentification/output/custom_reid_map.json
```

**Note**: 
- If `--output` is not specified, filename is auto-generated: `{doc_id}_page_{page_number}_reidentified.txt`
- If `--reid-map-output` is not specified, filename is auto-generated: `reid_map_{doc_id}.json` (document-level, constant per document)

## How It Works

1. **Loads metadata**: Reads the JSON metadata file containing all detected entities with their original text, positions, and entity IDs.
2. **Loads anonymized text**: Reads the anonymized text where PHI has been replaced with entity type tokens (e.g., `PERSON`, `DATE_TIME`).
3. **Reconstructs text**: Replaces each entity type token with the original text in the correct order.
4. **Saves outputs**: Writes the re-identified text and a reusable mapping file.

## Output Files

All re-identification outputs are saved in `reidentification/output/`:

### Per-Page Files:
- **`{doc_id}_page_{page_number}_reidentified.txt`**: The restored original text with all PHI restored (one file per page).

### Document-Level Files:
- **`reid_map_{doc_id}.json`**: A document-level mapping file that contains all pages. Structure:
  ```json
  {
    "doc_name": "...",
    "doc_id": "...",
    "pages": {
      "1": {
        "replacements": [...]
      },
      "2": {
        "replacements": [...]
      }
    }
  }
  ```

**Key Features**:
- Re-identified text files are generated per page (e.g., `LLM_output_page_1_reidentified.txt`, `LLM_output_page_2_reidentified.txt`)
- Re-ID map is **constant per document** (e.g., `reid_map_LLM_output.json`) and supports multiple pages
- When processing multiple pages of the same document, the re-ID map is automatically merged/updated
- This structure is flexible for multi-page documents

**Note**: The script reads from the main `output/` folder (de-identification outputs) but writes its own outputs to `reidentification/output/` to keep them separate.

## Notes

- This module is **standalone** and does not import any code from the de-identification pipeline.
- It only depends on standard library modules (`argparse`, `json`, `os`, `pathlib`).
- Currently supports single-page re-identification. Multi-page support can be added later.
