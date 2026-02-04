from __future__ import annotations

import asyncio
import json
import sys
import os
from typing import Dict, Any, List
from pathlib import Path

from app.config.settings import get_settings


class DeidService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ensemble_module_path = Path(__file__).parent.parent.parent.parent / "Ensemble_DEID"
        self._initialize_ensemble()
        
    def _initialize_ensemble(self) -> None:
        """Initialize ensemble deidentifier models."""
        try:
            # Add ensemble module to path if not already there
            ensemble_str = str(self.ensemble_module_path)
            if ensemble_str not in sys.path:
                sys.path.insert(0, ensemble_str)
            
            # Import and initialize models on first use
            self._ensemble_ready = True
        except Exception as e:
            print(f"Warning: Could not initialize ensemble module: {e}")
            self._ensemble_ready = False

    async def redact_phi(self, text: str) -> Dict[str, Any]:
        """
        De-identify text using ensemble method (Presidio + Stanford).
        
        Args:
            text: Text to de-identify
            
        Returns:
            Dictionary with structure:
            {
                'success': bool,
                'original_text': str,
                'deidentified_text': str,
                'entities_found': list,
                'entities_count': dict,
                'metadata': dict
            }
        """
        try:
            if not self._ensemble_ready:
                # Fallback to basic pattern matching
                return await self._basic_redaction(text)
            
            # Use ensemble deidentifier
            result = await self._ensemble_redact(text)
            return result
            
        except Exception as e:
            # Fallback to basic redaction on error
            print(f"Ensemble redaction error, falling back: {e}")
            return await self._basic_redaction(text)
    
    async def _ensemble_redact(self, text: str) -> Dict[str, Any]:
        """Use full ensemble approach (Presidio + Stanford + Custom Patterns) from Ensemble_DEID."""
        try:
            import sys
            ensemble_str = str(self.ensemble_module_path)
            if ensemble_str not in sys.path:
                sys.path.insert(0, ensemble_str)
            
            # Import components from ensemble_deidentifier
            from ensemble_deidentifier import (
                stanford_analyzer, 
                detect_postal_codes, 
                detect_address_numbers, 
                detect_age_values, 
                detect_gender_sex, 
                detect_abbreviated_doctor_names,
                presidio_to_dict,
                normalize_label,
                BLACKLISTED_TYPES,
                sanitize_entity,
                MEDICAL_DEGREE_BLACKLIST,
                DRUG_NAME_WHITELIST,
                is_medicine_context,
                overlap_fraction,
                normalized_span_key,
                to_recognizer_results
            )
            from presidio_anonymizer import AnonymizerEngine
            from presidio_anonymizer.entities import OperatorConfig
            import re

            # Run detection in a thread to avoid blocking
            def run_detection(text):
                # Run Stanford model
                stanford_results = presidio_to_dict(stanford_analyzer.analyze(text, language="en"), text)

                # Run custom pattern detectors
                postal_code_results = detect_postal_codes(text)
                address_number_results = detect_address_numbers(text)
                age_results = detect_age_values(text)
                gender_sex_results = detect_gender_sex(text)
                
                all_persons = [e for e in stanford_results if normalize_label(e.get("entity_type", "")) == "PERSON"]
                abbreviated_doctor_results = detect_abbreviated_doctor_names(text, all_persons)
                
                custom_results = postal_code_results + address_number_results + age_results + gender_sex_results + abbreviated_doctor_results
                for custom_entity in custom_results:
                    custom_entity["entity_type"] = normalize_label(custom_entity.get("entity_type", ""))
                    stanford_results.append(custom_entity.copy())
                
                return stanford_results

            stanford_results = await asyncio.to_thread(run_detection, text)

            # Ensemble Logic (simplified/ported from ensemble_deidentifier.py)
            core_types = {"PERSON", "LOCATION", "ORGANIZATION", "DATE_TIME", "PHONE_NUMBER", "ID", "POSTAL_CODE", "ADDRESS_NUMBER"}
            ensembled = []
            
            # 1) Non-core types
            for entity in stanford_results:
                etype = entity.get("entity_type")
                if etype in core_types or etype in BLACKLISTED_TYPES:
                    continue
                ensembled.append(sanitize_entity(entity))

            # 2) PERSON entities
            existing_person_spans = set()
            for ent in stanford_results:
                if normalize_label(ent.get("entity_type", "")) != "PERSON":
                    continue
                if ent.get("score", 0.0) < 0.5:
                    continue
                entity = sanitize_entity(ent)
                span_text = entity.get("text", "")
                txt_upper = span_text.strip().upper()
                
                # Filters
                if re.sub(r"[^\w]", "", txt_upper) in MEDICAL_DEGREE_BLACKLIST: continue
                if re.sub(r"[^\w\s]", "", span_text).strip().upper() in DRUG_NAME_WHITELIST: continue
                if txt_upper.isupper() and len(txt_upper) <= 4: continue
                if is_medicine_context(span_text, text, entity.get("start", 0), entity.get("end", 0)): continue
                
                start, end = entity.get("start", 0), entity.get("end", 0)
                if any(overlap_fraction(start, end, ps, pe) > 0.5 for ps, pe in existing_person_spans): continue
                
                existing_person_spans.add((start, end))
                ensembled.append(entity)

            # 3) Other Core types (simplified for integration)
            for ent in stanford_results:
                etype = normalize_label(ent.get("entity_type", ""))
                if etype not in {"ID", "PHONE_NUMBER", "DATE_TIME", "LOCATION", "ORGANIZATION", "POSTAL_CODE", "ADDRESS_NUMBER"}:
                    continue
                
                score = ent.get("score", 0.0)
                if etype == "ID" and score < 0.75: continue
                if etype == "PHONE_NUMBER" and score < 0.7: continue
                if etype == "DATE_TIME" and score < 0.7: continue
                if etype in {"LOCATION", "ORGANIZATION"} and score < 0.65: continue
                if etype in {"POSTAL_CODE", "ADDRESS_NUMBER"} and score < 0.6: continue
                
                ensembled.append(sanitize_entity(ent))

            # Deduplicate
            deduped = []
            seen_keys = set()
            for e in ensembled:
                k = normalized_span_key(e)
                if k in seen_keys or k == (None, "", None, None): continue
                seen_keys.add(k)
                deduped.append(e)
            ensembled = deduped

            # Anonymize
            anonymizer = AnonymizerEngine()
            rec_results = to_recognizer_results(ensembled)
            operators = {res.entity_type: OperatorConfig("replace", {"new_value": f"[{res.entity_type}]"}) for res in rec_results}
            if "DEFAULT" not in operators: operators["DEFAULT"] = OperatorConfig("replace", {"new_value": "ENTITY"})
            
            anonymized_result = anonymizer.anonymize(text=text, analyzer_results=rec_results, operators=operators)
            deidentified_text = anonymized_result.text

            return {
                'success': True,
                'original_text': text,
                'deidentified_text': deidentified_text,
                'entities_found': ensembled,
                'entities_count': {etype: sum(1 for e in ensembled if e['entity_type'] == etype) for etype in set(e['entity_type'] for e in ensembled)},
                'metadata': {
                    'method': 'ensemble_presidio_stanford_custom',
                    'model': 'StanfordAIMI/stanford-deidentifier-base'
                }
            }
            
        except Exception as e:
            # Fallback to basic redaction
            return await self._basic_redaction(text)
    
    async def _basic_redaction(self, text: str) -> Dict[str, Any]:
        """Basic redaction using regex patterns."""
        await asyncio.sleep(0)  # yield control
        
        import re
        
        patterns = {
            'SSN': r'\b\d{3}-\d{2}-\d{4}\b',
            'PHONE': r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
            'EMAIL': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'DATE': r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{1,2}-\d{1,2}\b',
            'PATIENT_ID': r'\bPID\s*:?\s*\d+\b',
            'MRN': r'\bMRN\s*:?\s*\d+\b',
        }
        
        deidentified_text = text
        entities_found = []
        entities_count = {}
        
        for entity_type, pattern in patterns.items():
            matches = list(re.finditer(pattern, deidentified_text, re.IGNORECASE))
            if matches:
                entities_count[entity_type] = len(matches)
                for match in matches:
                    entities_found.append({
                        'type': entity_type,
                        'start': match.start(),
                        'end': match.end(),
                        'score': 0.9,
                        'text': match.group()
                    })
                deidentified_text = re.sub(pattern, f'[{entity_type}]', deidentified_text, flags=re.IGNORECASE)
        
        return {
            'success': True,
            'original_text': text,
            'deidentified_text': deidentified_text,
            'entities_found': entities_found,
            'entities_count': entities_count,
            'metadata': {
                'method': 'regex_basic_redaction'
            }
        }


def get_deid_service() -> DeidService:
    return DeidService()

