import os
import json
import re
import logging
from abc import ABC, abstractmethod

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    def generate_materials(self, text: str) -> dict:
        pass


class GroqProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")

        # Fix: response_format must be set via .bind() on the chain, NOT in the
        # ChatGroq constructor. Passing it to the constructor is silently ignored
        # in langchain-groq >= 1.0, so the LLM returns free-form text and
        # json.loads fails, leaving all arrays empty.
        self.llm = ChatGroq(
            api_key=self.api_key,
            model="openai/gpt-oss-20b",
            temperature=0.3,
        )

        self.prompt = PromptTemplate.from_template(
            """You are an expert academic assistant. Analyze the following course/study text and generate comprehensive study materials in valid JSON format.

The JSON MUST have EXACTLY this structure:
{{
    "important_questions": [
        {{"question": "...", "priority": "High"}}
    ],
    "mcqs": [
        {{"question": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "correct_answer": "A. ..."}}
    ],
    "fill_in_the_blanks": [
        {{"sentence": "The ____ is responsible for ...", "answer": "..."}}
    ],
    "short_questions": [
        {{"question": "...", "answer": "..."}}
    ],
    "long_questions": [
        {{"question": "...", "answer": "..."}}
    ]
}}

Rules:
- Generate at least 5 items per category when enough content exists.
- priority must be one of: "High", "Medium", or "Low"
- Each MCQ must have exactly 4 options and one correct_answer that matches one of the options exactly.
- Return ONLY valid JSON, no markdown, no explanation, no preamble.

Text to analyze:
{text}
"""
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=10000,
            chunk_overlap=500,
        )

    def _extract_json(self, raw: str) -> dict:
        """Robustly extract JSON from LLM response, stripping markdown fences if present."""
        cleaned = raw.strip()
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

        # Find the outermost JSON object if there's any trailing text
        brace_start = cleaned.find('{')
        brace_end = cleaned.rfind('}')
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            cleaned = cleaned[brace_start:brace_end + 1]

        return json.loads(cleaned)

    def generate_materials(self, text: str) -> dict:
        chunks = self.text_splitter.split_text(text)

        # Limit to 10 chunks to avoid rate-limit issues (~100k chars max)
        chunks = chunks[:10]

        aggregated_materials = {
            "important_questions": [],
            "mcqs": [],
            "fill_in_the_blanks": [],
            "short_questions": [],
            "long_questions": [],
        }

        # Fix: bind response_format at chain build time so Groq JSON mode is
        # properly activated via the API. This ensures the model always returns
        # valid JSON rather than plain text wrapped in markdown fences.
        llm_json = self.llm.bind(response_format={"type": "json_object"})
        chain = self.prompt | llm_json

        for idx, chunk in enumerate(chunks):
            try:
                logger.info(f"Processing chunk {idx + 1}/{len(chunks)} (length={len(chunk)})...")

                response = chain.invoke({"text": chunk})

                # Log the raw response for debugging before parsing
                raw_content = response.content
                logger.debug(f"Raw LLM response for chunk {idx + 1}: {raw_content[:300]}")

                try:
                    content_json = self._extract_json(raw_content)

                    # Merge arrays from this chunk into aggregated result
                    merged_count = 0
                    for key in aggregated_materials:
                        if key in content_json and isinstance(content_json[key], list):
                            aggregated_materials[key].extend(content_json[key])
                            merged_count += len(content_json[key])

                    logger.info(
                        f"Chunk {idx + 1}: merged {merged_count} items across all categories."
                    )

                except (json.JSONDecodeError, ValueError) as json_err:
                    logger.error(
                        f"Failed to decode JSON from chunk {idx + 1}: {json_err}\n"
                        f"Raw response (first 800 chars): {raw_content[:800]}"
                    )
                    continue

            except Exception as e:
                logger.error(f"Error calling Groq API on chunk {idx + 1}: {e}", exc_info=True)
                continue

        total = sum(len(v) for v in aggregated_materials.values())
        logger.info(f"Generation complete. Total items across all categories: {total}")
        return aggregated_materials


class LLMService:
    def __init__(self, provider: LLMProvider = None):
        self.provider = provider or GroqProvider()

    def get_study_materials(self, text: str) -> dict:
        if not text or not text.strip():
            raise ValueError("Extracted PDF text is empty. The PDF may be scanned/image-based.")
        return self.provider.generate_materials(text)
