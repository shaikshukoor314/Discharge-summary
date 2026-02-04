import sys
import io
import os
from openai import OpenAI
from typing import Optional

# Force UTF-8 encoding on stdout to handle all Unicode characters safely
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class LLMPipeline:
    """
    LLM-based pipeline for medical terminology spell checking using the Groq API.
    """

    def __init__(self, api_key: Optional[str] = None):
        # Get API key from environment variable or parameter
        # Set GROQ_API_KEY environment variable before running
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set. Please set it before running.")

        # Initialize Groq client (OpenAI compatible)
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=self.api_key
        )
        self.model = "llama-3.1-8b-instant"
        self.temperature = 0.1
        self.max_tokens = 2048

        # Detailed, safety-focused clinical prompt for consistent corrections
        self.system_prompt = """Your task is to clean and correct spelling errors in the given medical text while preserving the original wording, abbreviations, nicknames, and informal clinical usage.
Follow these exact rules:
Instructions:
Preserve the exact line breaks, spacing, and indentation of the original text exactly as in the input.
Do NOT change formatting or add/remove blank lines.
Only correct spelling mistakes.
Do NOT expand abbreviations (e.g., keep CKD, HTN, DM as-is).
Do NOT convert nicknames, brand names, or informal terms into scientific or generic names.
Do NOT replace abbreviations with full forms.
Do NOT introduce scientific terminology if the original uses short or informal forms.
Correct spelling only if it is clearly incorrect.
Remove unwanted characters, stray symbols, and encoding artifacts (such as "@@", "#", "~", "*", "@") only if they are accidental.
Preserve meaning, order, and structure.
Do NOT rephrase, rewrite, or summarize.
Do NOT add explanations or extra text.
Output only the corrected text.
"""

    def check_spelling(self, input_text: str, model: Optional[str] = None) -> str:
        """Perform medical spell checking using the Groq API."""
        if not input_text or not input_text.strip():
            return input_text

        try:
            response = self.client.chat.completions.create(
                model=model or self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": input_text},
                ],
            )
            corrected_text = response.choices[0].message.content
            if not corrected_text:
                raise RuntimeError("Empty response from Groq API.")
            return corrected_text.strip()

        except Exception as e:
            raise RuntimeError(f"Error during spell checking: {str(e)}")

    def process(self, input_text: str) -> str:
        return self.check_spelling(input_text)


def main():
    try:
        pipeline = LLMPipeline()
    except ValueError as e:
        print(f"Error initializing pipeline: {e}")
        return

    input_file = "LLM_input.txt"
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read().strip()
    except Exception as e:
        print(f"Error reading {input_file}: {e}")
        return

    if not input_text:
        print(f"No input found in {input_file}. Exiting.")
        return

    try:
        corrected_output = pipeline.process(input_text)
        print("\nCorrected Text:")
        print("-" * 60)
        print(corrected_output)

        output_file = "LLM_output.txt"
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(corrected_output)
            print(f"\nOutput saved to {output_file}")
        except Exception as e:
            print(f"Error saving output to {output_file}: {e}")

    except Exception as e:
        print(f"\nError processing text: {e}")


if __name__ == "__main__":
    sys.argv = [sys.argv[0]]  # Clean argv for environments like Jupyter
    main()
