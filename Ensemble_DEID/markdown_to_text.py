"""
Markdown to Text Converter

This script converts markdown format to plain text while preserving layout,
especially tables and other structured elements.
"""

import sys
import io
import re
from pathlib import Path

# Force UTF-8 encoding on stdout to handle all Unicode characters safely
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def html_table_to_text(html_table: str) -> str:
    """
    Convert an HTML table to a formatted text table with layout retention.
    
    Args:
        html_table: HTML table string (e.g., <table>...</table>)
        
    Returns:
        Formatted text table string
    """
    # Extract all table rows
    rows = []
    
    # Find all <tr>...</tr> blocks
    tr_pattern = r'<tr[^>]*>(.*?)</tr>'
    tr_matches = re.findall(tr_pattern, html_table, re.DOTALL | re.IGNORECASE)
    
    for tr_content in tr_matches:
        row_cells = []
        
        # Extract header cells <th>...</th>
        th_pattern = r'<th[^>]*>(.*?)</th>'
        th_matches = re.findall(th_pattern, tr_content, re.DOTALL | re.IGNORECASE)
        for th in th_matches:
            # Remove nested tags and clean text
            cell_text = re.sub(r'<[^>]+>', '', th).strip()
            row_cells.append((cell_text, 1))  # Headers have no colspan
        
        # Extract data cells <td>...</td> with full tag to check attributes
        td_full_pattern = r'<td([^>]*)>(.*?)</td>'
        td_matches = re.findall(td_full_pattern, tr_content, re.DOTALL | re.IGNORECASE)
        for td_attrs, td_content in td_matches:
            # Remove nested tags and clean text (preserve leading/trailing content including asterisks)
            # First remove all HTML tags
            cell_text = re.sub(r'<[^>]+>', '', td_content)
            # Strip only whitespace, preserve asterisks and other characters
            cell_text = cell_text.strip()
            # Handle colspan attribute for this specific td
            colspan_match = re.search(r'colspan=["\']?(\d+)["\']?', td_attrs, re.IGNORECASE)
            if colspan_match:
                colspan_count = int(colspan_match.group(1))
                # Store colspan info as a tuple (text, colspan_count)
                row_cells.append((cell_text, colspan_count))
            else:
                row_cells.append((cell_text, 1))
        
        if row_cells:
            rows.append(row_cells)
    
    if not rows:
        return html_table  # Return original if parsing fails
    
    # Calculate column widths properly
    # First, determine number of columns from header row or max row length
    num_cols = 0
    for row in rows:
        col_count = 0
        for cell_data in row:
            if isinstance(cell_data, tuple):
                col_count += cell_data[1]  # colspan count
            else:
                col_count += 1
        num_cols = max(num_cols, col_count)
    
    if num_cols == 0:
        return html_table
    
    col_widths = [0] * num_cols
    
    # Calculate widths from all cells
    for row in rows:
        col_idx = 0
        for cell_data in row:
            if isinstance(cell_data, tuple):
                cell_text, colspan = cell_data
                # For colspan cells, distribute width requirement
                actual_colspan = min(colspan, num_cols - col_idx)
                if actual_colspan > 0:
                    per_col = max(len(cell_text) // actual_colspan, 10)
                    for i in range(actual_colspan):
                        if col_idx + i < num_cols:
                            col_widths[col_idx + i] = max(col_widths[col_idx + i], per_col)
                col_idx += colspan
            else:
                cell_text = cell_data if isinstance(cell_data, str) else ""
                if col_idx < num_cols:
                    col_widths[col_idx] = max(col_widths[col_idx], len(cell_text))
                col_idx += 1
    
    # Set appropriate minimum column widths based on typical medical chart structure
    # S. No. should be narrow, DRUG column should be widest
    if num_cols >= 2:
        col_widths[0] = max(col_widths[0], 8)  # S. No. - narrow
        col_widths[1] = max(col_widths[1], 25)  # DRUG - widest
    for i in range(num_cols):
        col_widths[i] = max(col_widths[i], 10)
    
    # Build text table with proper formatting
    text_lines = []
    header_added = False
    
    for row_idx, row in enumerate(rows):
        # Check if this row has colspan cells
        has_colspan = any(isinstance(cell, tuple) and cell[1] > 1 for cell in row)
        
        if has_colspan:
            # Handle colspan rows - merge spanned columns
            row_parts = []
            col_idx = 0
            for cell_data in row:
                if isinstance(cell_data, tuple):
                    cell_text, colspan = cell_data
                    # Calculate total width for spanned columns (including spacing)
                    actual_colspan = min(colspan, num_cols - col_idx)
                    if actual_colspan > 0:
                        span_width = sum(col_widths[col_idx + i] for i in range(actual_colspan)) + (actual_colspan - 1) * 2  # 2 spaces between columns
                        # If this is the first cell and it spans from column 0, align it properly
                        if col_idx == 0:
                            row_parts.append(cell_text.ljust(max(span_width, len(cell_text))))
                        else:
                            row_parts.append(cell_text.ljust(max(span_width, len(cell_text))))
                    col_idx += colspan
                else:
                    # Regular cell
                    cell_text = cell_data if isinstance(cell_data, str) else ""
                    if col_idx < num_cols:
                        row_parts.append(cell_text.ljust(col_widths[col_idx]))
                    col_idx += 1
            # Join with proper spacing, but ensure colspan rows align from start
            if row_parts:
                text_lines.append("  ".join(row_parts))
        else:
            # Regular row - pad cells to match column widths
            padded_cells = []
            for i in range(num_cols):
                if i < len(row):
                    cell_data = row[i]
                    cell_text = cell_data[0] if isinstance(cell_data, tuple) else (cell_data if isinstance(cell_data, str) else "")
                else:
                    cell_text = ""
                padded_cells.append(cell_text.ljust(col_widths[i]))
            
            # Join with consistent spacing (2 spaces between columns)
            row_text = "  ".join(padded_cells)
            text_lines.append(row_text)
        
        # Add separator line after header row (first row)
        if not header_added and row_idx == 0:
            # Create separator line with dashes matching exact column widths
            separator_parts = []
            for i in range(num_cols):
                separator_parts.append("-" * col_widths[i])
            separator = "  ".join(separator_parts)
            text_lines.append(separator)
            header_added = True
    
    return "\n".join(text_lines)


def markdown_table_to_text(markdown_table: str) -> str:
    """
    Convert a markdown table to a formatted text table with layout retention.
    
    Args:
        markdown_table: Markdown table string
        
    Returns:
        Formatted text table string
    """
    lines = markdown_table.strip().split('\n')
    if not lines:
        return ""
    
    # Parse table rows
    rows = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('|') is False:
            continue
        # Remove leading/trailing pipes and split by pipe
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if cells:  # Only add non-empty rows
            rows.append(cells)
    
    if not rows:
        return markdown_table  # Return original if parsing fails
    
    # Skip separator row (usually contains dashes)
    data_rows = [row for row in rows if not all(re.match(r'^[\s\-:]+$', cell) for cell in row)]
    
    if not data_rows:
        return markdown_table
    
    # Calculate column widths
    num_cols = max(len(row) for row in data_rows) if data_rows else 0
    if num_cols == 0:
        return markdown_table
    
    col_widths = [0] * num_cols
    for row in data_rows:
        for i, cell in enumerate(row[:num_cols]):
            col_widths[i] = max(col_widths[i], len(cell))
    
    # Build text table
    text_lines = []
    for row in data_rows:
        # Pad cells to match column widths
        padded_cells = []
        for i in range(num_cols):
            cell = row[i] if i < len(row) else ""
            padded_cells.append(cell.ljust(col_widths[i]))
        
        # Join with spaces (or use | for better separation)
        text_lines.append("  ".join(padded_cells))
    
    return "\n".join(text_lines)


def markdown_to_text(markdown_content: str) -> str:
    """
    Convert markdown content to plain text while preserving layout.
    
    Args:
        markdown_content: Markdown formatted text
        
    Returns:
        Plain text with layout preserved
    """
    text = markdown_content
    
    # Convert HTML tables to text tables first (OCR output contains HTML tables)
    html_table_pattern = r'(<table[^>]*>.*?</table>)'
    
    def replace_html_table(match):
        table_html = match.group(1)
        return html_table_to_text(table_html) + "\n"
    
    text = re.sub(html_table_pattern, replace_html_table, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert markdown tables to text tables (for standard markdown format)
    # Pattern to match markdown tables (lines starting with |)
    markdown_table_pattern = r'(\|.+\|\n(?:\|[\s\-:]+\|\n)?(?:\|.+\|\n?)+)'
    
    def replace_markdown_table(match):
        table_md = match.group(1)
        return markdown_table_to_text(table_md) + "\n"
    
    text = re.sub(markdown_table_pattern, replace_markdown_table, text, flags=re.MULTILINE)
    
    # Remove markdown headers (keep text, remove #)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)
    
    # Remove markdown bold/italic markers (keep text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Italic
    text = re.sub(r'__([^_]+)__', r'\1', text)  # Bold alt
    text = re.sub(r'_([^_]+)_', r'\1', text)  # Italic alt
    
    # Remove markdown links but keep text: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # Remove markdown images: ![alt](url) -> alt
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
    
    # Remove markdown code blocks (keep content)
    text = re.sub(r'```[\s\S]*?```', '', text)  # Code blocks
    text = re.sub(r'`([^`]+)`', r'\1', text)  # Inline code
    
    # Remove markdown horizontal rules
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    
    # Remove markdown list markers but preserve indentation
    text = re.sub(r'^\s*[-*+]\s+', '  ', text, flags=re.MULTILINE)  # Unordered lists
    text = re.sub(r'^\s*\d+\.\s+', '  ', text, flags=re.MULTILINE)  # Ordered lists
    
    # Clean up multiple blank lines (keep max 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text.strip()


def main():
    """Main function to convert Ocr_output.md to LLM_input.txt"""
    input_file = Path("Ocr_output.md")
    output_file = Path("LLM_input.txt")
    
    if not input_file.exists():
        print(f"Error: {input_file} not found.")
        print("Please run chandra_ocr_client.py first to generate Ocr_output.md")
        return
    
    try:
        # Read markdown content
        with open(input_file, "r", encoding="utf-8") as f:
            markdown_content = f.read()
        
        # Convert to text
        text_content = markdown_to_text(markdown_content)
        
        # Write to output file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text_content)
        
        print(f"✓ Converted {input_file} to {output_file}")
        print(f"  Layout preserved (tables, structure, etc.)")
        
    except Exception as e:
        print(f"Error converting markdown to text: {e}")


if __name__ == "__main__":
    main()

