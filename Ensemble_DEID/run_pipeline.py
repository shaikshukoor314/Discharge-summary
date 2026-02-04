import subprocess
import sys
import os

# Paths
markdown_converter_script = "markdown_to_text.py"
llm_script = "LLM.py"
deid_script = "ensemble_deidentifier.py"
output_dir = "output"

# Step 1: Convert Ocr_output.md to LLM_input.txt (markdown to text with layout retention)
print("[Pipeline] Converting markdown to text...")
convert_result = subprocess.run([sys.executable, markdown_converter_script], capture_output=True, text=True)
print(convert_result.stdout)
if convert_result.returncode != 0:
    print(f"markdown_to_text.py failed: {convert_result.stderr}")
    sys.exit(1)

# Step 2: Run LLM.py (input: LLM_input.txt, output: LLM_output.txt)
print("[Pipeline] Running LLM.py...")
llm_result = subprocess.run([sys.executable, llm_script], capture_output=True, text=True)
print(llm_result.stdout)
if llm_result.returncode != 0:
    print(f"LLM.py failed: {llm_result.stderr}")
    sys.exit(1)

# Step 3: Run ensemble_deidentifier.py (input: LLM_output.txt, output: output/anonymized_output.txt)
print("[Pipeline] Running ensemble_deidentifier.py...")
deid_result = subprocess.run([sys.executable, deid_script], capture_output=True, text=True)
print(deid_result.stdout)
if deid_result.returncode != 0:
    print(f"ensemble_deidentifier.py failed: {deid_result.stderr}")
    sys.exit(1)

print(f"[Pipeline] Complete. Check the '{output_dir}' folder for results.")
