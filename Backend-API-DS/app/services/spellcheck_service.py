from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any
from app.config.settings import get_settings


class SpellcheckService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ensemble_module_path = Path(__file__).parent.parent.parent.parent / "Ensemble_DEID"
        self._pipeline = None
        self._initialize_pipeline()

    def _initialize_pipeline(self) -> None:
        """Initialize LLM pipeline for spell checking."""
        try:
            import sys
            ensemble_str = str(self.ensemble_module_path)
            if ensemble_str not in sys.path:
                sys.path.insert(0, ensemble_str)
            
            from LLM import LLMPipeline
            api_key = self.settings.groq_api_key or os.getenv("GROQ_API_KEY")
            if api_key:
                self._pipeline = LLMPipeline(api_key=api_key)
            else:
                print("Warning: GROQ_API_KEY not found. Spellcheck will use basic fallback.")
        except Exception as e:
            print(f"Warning: Could not initialize LLMPipeline: {e}")

    async def correct_text(self, text: str) -> Dict[str, Any]:
        """
        Perform spell check and correction on OCR text.
        """
        try:
            if self._pipeline:
                # Run the pipeline in a thread to avoid blocking the event loop
                corrected_text = await asyncio.to_thread(self._pipeline.process, text)
            else:
                corrected_text = await self._apply_basic_corrections(text)
            
            corrections_made = self._count_corrections(text, corrected_text)
            
            return {
                'success': True,
                'original_text': text,
                'corrected_text': corrected_text,
                'corrections_made': corrections_made,
                'metadata': {
                    'method': 'llm_groq' if self._pipeline else 'basic_correction'
                }
            }
        except Exception as e:
            return {
                'success': False,
                'original_text': text,
                'corrected_text': text,
                'error': str(e),
                'corrections_made': 0,
                'metadata': {}
            }
    
    async def _apply_basic_corrections(self, text: str) -> str:
        """Apply basic spell corrections to text."""
        await asyncio.sleep(0)  # yield control
        
        # Common medical OCR corrections
        corrections = {
            r'\b(teh)\b': 'the',
            r'\b(recieve)\b': 'receive',
            r'\b(seperate)\b': 'separate',
            r'\b(occured)\b': 'occurred',
            r'\b(becuz)\b': 'because',
            r'\b(dise|desease)\b': 'disease',
        }
        
        import re
        corrected = text
        for pattern, replacement in corrections.items():
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
        
        return corrected
    
    def _count_corrections(self, original: str, corrected: str) -> int:
        """Count number of corrections made."""
        import difflib
        matcher = difflib.SequenceMatcher(None, original, corrected)
        # Count non-matching blocks as corrections
        return sum(1 for match in matcher.get_opcodes() if match[0] != 'equal')


def get_spellcheck_service() -> SpellcheckService:
    return SpellcheckService()

