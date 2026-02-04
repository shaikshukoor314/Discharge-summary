# Medical De-Identification Pipeline

A comprehensive medical text de-identification system that combines LLM-based spell checking with advanced Named Entity Recognition (NER) to detect and redact Protected Health Information (PHI) from medical documents.

## Features

- **LLM-Based Spell Checking**: Uses Groq API (Llama 3.1) for medical terminology correction and normalization
- **Advanced NER Detection**: StanfordAIMI medical domain-specific model for accurate PHI detection
- **Comprehensive Entity Detection**: Detects and redacts:
  - **PERSON**: Patient names, doctor names, staff names
  - **LOCATION**: Hospitals, clinics, addresses
  - **ORGANIZATION**: Medical facilities, diagnostic centers
  - **PHONE_NUMBER**: Contact numbers
  - **DATE_TIME**: Dates and timestamps
  - **ID**: Patient IDs, registration numbers
  - **POSTAL_CODE**: Indian postal codes
  - **ADDRESS_NUMBER**: Address identifiers
  - **AGE**: Patient age values
  - **GENDER**: Gender/sex identifiers
  - **EMAIL_ADDRESS**: Email addresses
- **Medical Domain Filters**: Excludes medical degrees (MD, MBBS, etc.) and drug names from person detection
- **Custom Pattern Detection**: Regex-based detection for Indian postal codes, address numbers, age, and gender

## Prerequisites

- **Python**: 3.8 or higher
- **Operating System**: Windows, Linux, or macOS
- **API Key**: Groq API key for LLM spell checking ([Get one here](https://console.groq.com/))
- **Hardware**: CPU-based execution (GPU optional but not required)

## Installation Steps

### 1. Clone or Download the Project

```bash
# If using git
git clone <repository-url>
cd Ensemble_DEID

# Or extract the project folder to your desired location
```

### 2. Create a Virtual Environment

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Download spaCy English Model

```bash
python -m spacy download en_core_web_sm
```

**Note**: The StanfordAIMI model (`StanfordAIMI/stanford-deidentifier-base`) will be automatically downloaded on first run.

### 5. Set Up API Key

Set the `GROQ_API_KEY` environment variable:

**Windows (PowerShell):**
```powershell
$env:GROQ_API_KEY="your-api-key-here"
```

**Windows (Command Prompt):**
```cmd
set GROQ_API_KEY=your-api-key-here
```

**Linux/macOS:**
```bash
export GROQ_API_KEY="your-api-key-here"
```

**Permanent Setup (Windows):**
1. Open System Properties → Environment Variables
2. Add new User variable: `GROQ_API_KEY` with your API key value

**Permanent Setup (Linux/macOS):**
Add to `~/.bashrc` or `~/.zshrc`:
```bash
export GROQ_API_KEY="your-api-key-here"
```

## Usage

### Quick Start

1. **Run OCR** (if processing PDF/image):
   ```bash
   python chandra_ocr_client.py
   ```
   - Input: `sample-1.pdf`
   - Output: `Ocr_output.md` (markdown format)

2. **Run the Pipeline**:
   ```bash
   python run_pipeline.py
   ```
   This will:
   - Convert `Ocr_output.md` to `LLM_input.txt` (markdown to text with layout retention)
   - Run spell checking via Groq API
   - Run de-identification via StanfordAIMI

3. **Check Results**: Output files will be in the `output/` folder.

### Pipeline Flow

```
sample-1.pdf
    ↓
[chandra_ocr_client.py] → OCR via Chandra OCR API
    ↓
Ocr_output.md (markdown format)
    ↓
[markdown_to_text.py] → Convert markdown to text (preserves tables/layout)
    ↓
LLM_input.txt
    ↓
[LLM.py] → Medical spell checking via Groq API
    ↓
LLM_output.txt
    ↓
[ensemble_deidentifier.py] → PHI detection & redaction via StanfordAIMI
    ↓
output/
    ├── anonymized_output.txt      # Final redacted text
    ├── ensemble_entities.json     # All detected entities
    ├── ensemble_metadata.json     # Processing metadata
    └── stanford_output.json       # Raw Stanford model output
```

### Running Individual Scripts

**Run OCR only:**
```bash
python chandra_ocr_client.py
```
- Input: `sample-1.pdf`
- Output: `Ocr_output.md`

**Convert markdown to text only:**
```bash
python markdown_to_text.py
```
- Input: `Ocr_output.md`
- Output: `LLM_input.txt`

**Run LLM spell checking only:**
```bash
python LLM.py
```
- Input: `LLM_input.txt`
- Output: `LLM_output.txt`

**Run de-identification only:**
```bash
python ensemble_deidentifier.py
```
- Input: `LLM_output.txt`
- Output: `output/` folder

## Project Structure

```
Ensemble_DEID/
│
├── run_pipeline.py              # Main pipeline orchestrator
├── LLM.py                       # LLM-based spell checking
├── ensemble_deidentifier.py    # De-identification engine
├── requirements.txt            # Python dependencies
├── README.md                   # This file
│
├── chandra_ocr_client.py       # OCR API client
├── markdown_to_text.py         # Markdown to text converter
├── Ocr_output.md               # OCR output (markdown format)
├── LLM_input.txt               # Input file for spell checking
├── LLM_output.txt              # Output from LLM (input for DEID)
│
└── output/                      # De-identification outputs
    ├── anonymized_output.txt
    ├── ensemble_entities.json
    ├── ensemble_metadata.json
    └── stanford_output.json
```

## Entity Detection Thresholds

The following score thresholds are used for entity detection:

| Entity Type | Model | Threshold | Notes |
|------------|-------|-----------|-------|
| PERSON | StanfordAIMI | ≥ 0.5 | Filters medical degrees, drug names |
| LOCATION | StanfordAIMI | ≥ 0.65 | Facility/address heuristics applied |
| ORGANIZATION | StanfordAIMI | ≥ 0.7 | Facility keywords considered |
| DATE_TIME | StanfordAIMI | ≥ 0.7 | Includes time extension |
| PHONE_NUMBER | StanfordAIMI | ≥ 0.7 | No pattern validation |
| ID | StanfordAIMI | ≥ 0.75 | Patient/registration IDs |
| POSTAL_CODE | StanfordAIMI + Custom | ≥ 0.6 | Indian postal codes |
| ADDRESS_NUMBER | StanfordAIMI + Custom | ≥ 0.6 | Address identifiers |

## Output Files

### `anonymized_output.txt`
Final redacted text with all detected PHI replaced by entity type labels (e.g., `[PERSON]`, `[PHONE_NUMBER]`).

### `ensemble_entities.json`
Complete list of all detected entities with:
- `entity_type`: Type of detected entity
- `text`: Original text span
- `score`: Confidence score (0.0-1.0)
- `start`: Character start position
- `end`: Character end position

### `ensemble_metadata.json`
Processing metadata including:
- Input file name
- Timestamp
- Models used
- Total entities detected
- Complete entity list

### `stanford_output.json`
Raw output from StanfordAIMI model before filtering and post-processing.

## Configuration

### Customizing Entity Detection

Edit `ensemble_deidentifier.py` to adjust:
- **Thresholds**: Modify score thresholds in the `main()` function
- **Medical Degree Blacklist**: Update `MEDICAL_DEGREE_BLACKLIST` (line 21-25)
- **Drug Whitelist**: Update `DRUG_NAME_WHITELIST` (line 28-32)
- **Facility Keywords**: Modify `facility_keywords` list (line 646-650)

### LLM Configuration

Edit `LLM.py` to customize:
- **Model**: Change `self.model` (default: `"llama-3.1-8b-instant"`)
- **Temperature**: Adjust `self.temperature` (default: `0.1`)
- **Max Tokens**: Modify `self.max_tokens` (default: `2048`)

## Troubleshooting

### Common Issues

**1. `GROQ_API_KEY` not set**
```
Error: GROQ_API_KEY environment variable is not set
```
**Solution**: Set the environment variable as described in Installation Step 5.

**2. Module not found errors**
```
ModuleNotFoundError: No module named 'presidio_analyzer'
```
**Solution**: Ensure virtual environment is activated and run `pip install -r requirements.txt`.

**3. spaCy model not found**
```
OSError: Can't find model 'en_core_web_sm'
```
**Solution**: Run `python -m spacy download en_core_web_sm`.

**4. File not found errors**
```
FileNotFoundError: [Errno 2] No such file or directory: 'LLM_input.txt'
```
**Solution**: Run `python chandra_ocr_client.py` first to generate `Ocr_output.md`, then run `python markdown_to_text.py` to create `LLM_input.txt`. Alternatively, create `LLM_input.txt` manually in the project root with your medical text.

**5. Slow execution (1-2 minutes)**
This is normal for CPU-based execution. The StanfordAIMI model loads on first run and processes text sequentially.

**6. Empty output**
- Check that `Ocr_output.md` exists (run `chandra_ocr_client.py` first)
- Check that `LLM_input.txt` contains text (run `markdown_to_text.py` if needed)
- Verify `LLM_output.txt` was created after LLM step
- Check console output for error messages

### Performance Tips

- **First Run**: Initial execution may take longer due to model downloads
- **Subsequent Runs**: Faster as models are cached
- **Large Documents**: Consider splitting very large documents into smaller chunks

## Dependencies

Key dependencies (see `requirements.txt` for complete list):
- `presidio-analyzer>=2.2.0`: Microsoft's PII detection framework
- `presidio-anonymizer>=2.2.0`: Anonymization engine
- `spacy>=3.7.0`: NLP framework
- `spacy-transformers>=1.3.0`: Transformers integration
- `transformers>=4.30.0`: Hugging Face transformers
- `torch>=2.0.0`: PyTorch for model execution
- `openai`: OpenAI-compatible API client (for Groq)

## License

[Specify your license here]

## Support

For issues or questions, please [create an issue](link-to-issues) or contact [your contact information].

## Version History

- **Current Version**: Uses StanfordAIMI model only (Flair and Stanza removed)
- **Pipeline**: Integrated LLM spell checking + De-identification
- **Entity Detection**: Comprehensive medical domain PHI detection

