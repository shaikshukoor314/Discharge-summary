import argparse
import json
import os
from pathlib import Path


def load_metadata(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_text(path: str, text: str) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)


def build_page_entities(metadata: dict, page_number: int) -> list:
    """
    For now we support a single page. We still accept a page number so that
    later you can extend this to true multi-page docs without changing
    the re-identification logic.
    """
    pages = metadata.get("pages") or {}
    page_key = str(page_number)
    if page_key in pages:
        # Use the richer page-wise view if present.
        by_type = pages[page_key].get("entities_by_type", {})
        entities = []
        for _etype, ents in by_type.items():
            entities.extend(ents)
        return entities

    # Fallback: use flat entities list.
    return metadata.get("entities", [])


def reidentify_text(anonymized_text: str, entities: list) -> str:
    """
    Reconstruct original text from anonymized text using entity metadata.

    Assumption (matches current de-identification):
      - Each redacted span is replaced by its entity_type string
        (e.g., 'PERSON', 'DATE_TIME', etc.).
      - We can safely re-identify by replacing occurrences of these
        tokens from left to right, in the same order as the original spans.
    """
    if not entities:
        return anonymized_text

    # Sort by original character position to approximate redaction order.
    sorted_entities = sorted(
        entities,
        key=lambda e: (e.get("start", 0), e.get("end", 0)),
    )

    text = anonymized_text
    # Track, per entity type, how far we've searched, so we always replace
    # the "next" occurrence of that type token.
    search_positions = {}

    for e in sorted_entities:
        etype = e.get("entity_type")
        original = e.get("text", "")
        if not etype or original is None:
            continue

        token = etype  # how de-identification replaced the span
        start_search = search_positions.get(etype, 0)
        idx = text.find(token, start_search)
        if idx == -1:
            # If we can't find this token, skip it to keep the rest stable.
            continue

        # Perform replacement: token -> original text.
        before = text[:idx]
        after = text[idx + len(token) :]
        text = before + original + after

        # Next time we search for this entity type, start after the
        # newly-inserted original text.
        search_positions[etype] = idx + len(original)

    return text


def build_reid_map(
    metadata: dict,
    entities: list,
    page_number: int,
) -> dict:
    """
    Build a document-wise, multi-page mapping which can be reused
    for future re-identification or auditing.
    Structure supports multiple pages per document.
    """
    doc_name = metadata.get("doc_name") or os.path.basename(metadata.get("input_file", ""))
    doc_id = metadata.get("doc_id") or os.path.splitext(doc_name)[0]

    replacements = []
    for idx, e in enumerate(
        sorted(entities, key=lambda x: (x.get("start", 0), x.get("end", 0)))
    ):
        replacements.append(
            {
                "order_index": idx,
                "entity_type": e.get("entity_type"),
                "original_text": e.get("text"),
                "replacement_token": e.get("entity_type"),
                "start": e.get("start"),
                "end": e.get("end"),
                "entity_id": e.get("entity_id"),
            }
        )

    # Multi-page structure: pages dict contains page_number -> replacements
    return {
        "doc_name": doc_name,
        "doc_id": doc_id,
        "pages": {
            str(page_number): {
                "replacements": replacements
            }
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Re-identify a single page using anonymized text and ensemble metadata.\n"
            "This is intentionally separate from the de-identification pipeline."
        )
    )
    # Path setup: read from main output/, write to reidentification/output/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    deid_output_dir = os.path.join(project_root, "output")  # Read from here
    reid_output_dir = os.path.join(script_dir, "output")     # Write to here
    
    parser.add_argument(
        "--metadata",
        default=os.path.join(deid_output_dir, "ensemble_metadata.json"),
        help="Path to ensemble metadata JSON produced by ensemble_deidentifier.py",
    )
    parser.add_argument(
        "--anonymized",
        default=os.path.join(deid_output_dir, "anonymized_output.txt"),
        help="Path to anonymized text file for this page",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=None,
        help="Page number to re-identify (if not specified, uses page_number from metadata)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Where to write the re-identified text (auto-generated from metadata if not specified)",
    )
    parser.add_argument(
        "--reid-map-output",
        default=None,
        help="Where to write the page-wise re-identification map (auto-generated from metadata if not specified)",
    )

    args = parser.parse_args()

    # Load metadata first to get doc_id and page_number for dynamic filenames
    metadata = load_metadata(args.metadata)
    anonymized_text = load_text(args.anonymized)
    
    # Determine page number (from args or metadata)
    page_number = args.page if args.page is not None else metadata.get("page_number", 1)
    
    # Get doc_id from metadata for filename construction
    doc_id = metadata.get("doc_id") or os.path.splitext(metadata.get("doc_name", "document"))[0] or "document"
    
    # Generate dynamic output filenames
    # Re-identified text: per page
    if args.output is None:
        args.output = os.path.join(reid_output_dir, f"{doc_id}_page_{page_number}_reidentified.txt")
    # Re-ID map: document-level (constant per doc_id, supports multi-page)
    if args.reid_map_output is None:
        args.reid_map_output = os.path.join(reid_output_dir, f"reid_map_{doc_id}.json")

    page_entities = build_page_entities(metadata, page_number)
    reidentified_text = reidentify_text(anonymized_text, page_entities)

    # Save reconstructed text
    save_text(args.output, reidentified_text)

    # Build page data for re-ID map
    page_reid_map = build_reid_map(metadata, page_entities, page_number)
    
    # Load existing re-ID map if it exists (for multi-page support)
    existing_reid_map = None
    if os.path.exists(args.reid_map_output):
        try:
            with open(args.reid_map_output, "r", encoding="utf-8") as f:
                existing_reid_map = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing_reid_map = None
    
    # Merge with existing map or create new one
    if existing_reid_map and existing_reid_map.get("doc_id") == doc_id:
        # Merge: add/update this page's data
        if "pages" not in existing_reid_map:
            existing_reid_map["pages"] = {}
        existing_reid_map["pages"][str(page_number)] = page_reid_map["pages"][str(page_number)]
        final_reid_map = existing_reid_map
    else:
        # New document or corrupted file: use new map
        final_reid_map = page_reid_map
    
    # Save the merged/updated re-ID map
    with open(args.reid_map_output, "w", encoding="utf-8") as f:
        json.dump(final_reid_map, f, indent=2, ensure_ascii=False)

    print(f"[Re-ID] Done. Re-identified page {page_number} (doc: {doc_id}) written to: {args.output}")
    print(f"[Re-ID] Document-level mapping saved to: {args.reid_map_output}")


if __name__ == "__main__":
    main()
