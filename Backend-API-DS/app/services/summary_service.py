"""Summary generation service using LLM."""
from __future__ import annotations

import json
import os
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

from app.utils.logger import get_logger

logger = get_logger(__name__)


class SummaryGenerationService:
    """Service for generating discharge summaries using LLM."""
    
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("GROQ_API_KEY not found. Summary generation will fail.")
            self.client = None
        else:
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.api_key
            )
        
        self.model = "llama-3.3-70b-versatile"  # Updated from decommissioned llama-3.1-70b-versatile
        self.temperature = 0.3
        self.max_tokens = 4096
    
    def generate_summary(
        self,
        validated_text: str,
        template: Dict[str, Any],
        patient_info: Dict[str, Any],
        custom_instructions: str | None = None
    ) -> Dict[str, Any]:
        """
        Generate a discharge summary using LLM.
        
        Args:
            validated_text: Validated OCR text from all pages
            template: Template structure with sections
            patient_info: Patient metadata (name, MRN, dates, etc.)
            custom_instructions: Optional additional instructions
            
        Returns:
            Dictionary containing structured summary content
        """
        if not self.client:
            raise RuntimeError("LLM client not initialized. GROQ_API_KEY missing.")
        
        # Build the system prompt with template structure
        system_prompt = self._build_system_prompt(template, patient_info)
        
        # Build user prompt with validated text
        user_prompt = self._build_user_prompt(validated_text, custom_instructions)
        
        try:
            logger.info(f"Generating summary with template: {template['name']}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            
            summary_text = response.choices[0].message.content
            if not summary_text:
                raise RuntimeError("Empty response from LLM API.")
            
            # Parse the LLM response into structured format
            summary_content = self._parse_summary_response(summary_text, template)
            
            logger.info("Summary generated successfully")
            return summary_content
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise RuntimeError(f"Failed to generate summary: {str(e)}")
    
    def _build_system_prompt(self, template: Dict[str, Any], patient_info: Dict[str, Any]) -> str:
        """Build the system prompt with template structure."""
        sections_list = "\n".join([f"- {section}" for section in template.get("sections", [])])
        
        prompt = f"""You are an expert medical documentation assistant specializing in creating discharge summaries.

**Your Task**: Generate a professional discharge summary based on the provided medical documentation.

**Template**: {template['name']} ({template['category']})
**Template Type**: {template['type']}

**Required Sections** (include ALL of these):
{sections_list}

**Patient Information**:
- Patient Name: {patient_info.get('name', 'Not provided')}
- MRN: {patient_info.get('mrn', 'Not provided')}
- DOB: {patient_info.get('dob', 'Not provided')}
- Gender: {patient_info.get('gender', 'Not provided')}
- Admission Date: {patient_info.get('admission_date', 'Not provided')}
- Discharge Date: {patient_info.get('discharge_date', 'Not provided')}

**Format Instructions**:
1. Output the summary in JSON format with section names as keys
2. Each section should be a string containing the relevant information
3. Use clear, professional medical language
4. Be concise but comprehensive
5. Ensure all medical terminology is accurate
6. Maintain HIPAA compliance - use only information provided

**Output Format**:
{{
    "patient_demographics": "...",
    "admission_information": "...",
    "hospital_course": "...",
    "diagnoses": "...",
    "medications": "...",
    "follow_up_instructions": "...",
    ...
}}

Return ONLY the JSON object, no other text."""
        
        return prompt
    
    def _build_user_prompt(self, validated_text: str, custom_instructions: str | None) -> str:
        """Build the user prompt with medical documentation."""
        prompt = f"""**Medical Documentation**:

{validated_text}

"""
        if custom_instructions:
            prompt += f"""**Additional Instructions**:
{custom_instructions}

"""
        
        prompt += "Please generate the discharge summary in JSON format as specified."
        return prompt
    
    def _parse_summary_response(self, llm_response: str, template: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the LLM response into structured format."""
        try:
            # Try to extract JSON from the response
            # Sometimes LLMs add markdown code blocks
            cleaned_response = llm_response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            
            summary_dict = json.loads(cleaned_response.strip())
            
            return {
                "template_id": template["id"],
                "template_name": template["name"],
                "sections": summary_dict
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.error(f"Response: {llm_response[:500]}...")
            
            # Fallback: return raw text
            return {
                "template_id": template["id"],
                "template_name": template["name"],
                "sections": {
                    "raw_summary": llm_response
                }
            }
