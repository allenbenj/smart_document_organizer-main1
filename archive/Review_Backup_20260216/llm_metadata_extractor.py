"""
LLM Metadata Extractor

Structured metadata extraction using LLM with regex-assisted hints.
Provides high-quality entity extraction with confidence scoring.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExtractedMetadata:
    """Structured metadata extracted from content"""
    doc_type: Optional[str] = None
    case_number: Optional[str] = None
    date: Optional[str] = None
    court: Optional[str] = None
    parties: List[str] = None
    judge: Optional[str] = None
    attorney: Optional[str] = None
    entities: Dict[str, List[str]] = None
    confidence: float = 0.0
    extraction_method: str = "none"
    
    def __post_init__(self):
        if self.parties is None:
            self.parties = []
        if self.entities is None:
            self.entities = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_type": self.doc_type,
            "case_number": self.case_number,
            "date": self.date,
            "court": self.court,
            "parties": self.parties,
            "judge": self.judge,
            "attorney": self.attorney,
            "entities": self.entities,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method
        }


class LLMMetadataExtractor:
    """
    Extract structured metadata using LLM with regex-assisted hints.
    
    Uses DeepSeek or other LLM to extract:
    - Document type (motion, complaint, order, etc.)
    - Case number
    - Date
    - Court name
    - Party names
    - Judge name
    - Attorney names
    - Other entities
    """
    
    ENTITY_PATTERNS = {
        'case_number': [
            r'(?:Case|No\.|#|Cause)\s*(?:No\.?)?\s*:?\s*(\d{2,4}[-]?[A-Z]{0,3}[-]?\d{3,7})',
            r'\b(\d{2}[A-Z]{2}\d{5,7})\b',
            r'(?:Docket|File)\s*(?:No\.?)?\s*:?\s*([A-Z0-9-]+)',
        ],
        'court': [
            r'(?:IN THE\s+)?([A-Z][A-Z\s]+(?:COURT|TRIBUNAL))',
            r'((?:Superior|District|Circuit|Family|Federal|Supreme|Municipal)\s+Court)',
        ],
        'judge': [
            r'(?:Judge|Hon\.|Honorable)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:JUDGE|HON\.)\s+([A-Z\s]+)',
        ],
        'attorney': [
            r'(?:Attorney|Counsel|Esq\.?)\s*:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:Esq\.|Attorney|Counsel)',
        ],
        'date': [
            r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b',
        ],
        'parties': [
            r'([A-Z][A-Z\s]+)\s+(?:v\.|vs\.?|versus)\s+([A-Z][A-Z\s]+)',
            r'(?:Plaintiff|Petitioner)[:\s]+([A-Z][a-zA-Z\s,]+)',
            r'(?:Defendant|Respondent)[:\s]+([A-Z][a-zA-Z\s,]+)',
        ],
        'amount': [
            r'\$\s*([\d,]+\.?\d*)',
            r'(\d{1,3}(?:,\d{3})+(?:\.\d{2})?)\s*(?:dollars|USD)',
        ],
        'phone': [
            r'\b(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\b',
            r'\((\d{3})\)\s*(\d{3})[-.\s]?(\d{4})',
        ],
        'email': [
            r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b',
        ],
    }

    EXTRACTION_PROMPT_TEMPLATE = """You are a legal document analysis expert. Extract structured metadata from this document.

Document Content (first 3000 characters):
---
{content}
---

Regex Hints (may be incomplete; use only if consistent with content):
{hints}

Extract the following information in JSON format:
{{
    "doc_type": "document type (motion, complaint, order, brief, etc.)",
    "case_number": "case number or docket number",
    "date": "document date in YYYY-MM-DD format",
    "court": "court name",
    "parties": ["plaintiff name", "defendant name"],
    "judge": "judge name",
    "attorney": "attorney name",
    "confidence": 0.0-1.0
}}

Rules:
1. Only include fields you can confidently extract
2. Use null for missing fields
3. Normalize dates to YYYY-MM-DD format
4. Set confidence based on how certain you are (0.0-1.0)
5. Respond ONLY with valid JSON, no additional text

JSON Response:"""

    def __init__(
        self,
        service_container: Optional[Any] = None,
        llm_model: Optional[Any] = None,
        use_cache: bool = True
    ):
        """
        Initialize metadata extractor.
        
        Args:
            service_container: ServiceContainer with LLM access
            llm_model: Direct LLM model instance
            use_cache: Cache extraction results
        """
        self.service_container = service_container
        self.llm_model = llm_model
        self.use_cache = use_cache
        self._cache: Dict[str, ExtractedMetadata] = {}
        
        # Get LLM from service container if available
        if service_container and not llm_model:
            try:
                self.llm_model = service_container.get_llm()
            except:
                logger.warning("Could not get LLM from service container")
        
        logger.info(f"LLMMetadataExtractor initialized (LLM: {self.llm_model is not None})")
    
    def extract(
        self,
        content: str,
        filename: Optional[str] = None,
        use_llm: bool = True,
        allow_regex_fallback: bool = True
    ) -> ExtractedMetadata:
        """
        Extract metadata from content.
        
        Args:
            content: Document content
            filename: Optional filename for context
            use_llm: Whether to use LLM (falls back to regex if False)
            
        Returns:
            ExtractedMetadata with confidence score
        """
        # Check cache
        if self.use_cache and content:
            cache_key = self._get_cache_key(content)
            if cache_key in self._cache:
                logger.debug("Using cached metadata")
                return self._cache[cache_key]
        
        # Try LLM extraction first
        if use_llm and self.llm_model:
            try:
                metadata = self._extract_with_llm(content, filename)
                if metadata.confidence > 0.0 or not allow_regex_fallback:
                    # Cache result
                    if self.use_cache:
                        self._cache[cache_key] = metadata
                    return metadata
                else:
                    logger.debug("LLM confidence too low; returning LLM result without fallback")
            except Exception as e:
                if not allow_regex_fallback:
                    logger.warning(f"LLM extraction failed with no fallback: {e}")
                    raise
                logger.warning(f"LLM extraction failed: {e}, returning empty result")
        
        metadata = ExtractedMetadata(extraction_method="llm")
        if self.use_cache:
            self._cache[cache_key] = metadata
        return metadata
    
    def _extract_with_llm(
        self,
        content: str,
        filename: Optional[str] = None
    ) -> ExtractedMetadata:
        """Extract metadata using LLM"""
        # Prepare content (limit to first 3000 chars for efficiency)
        content_sample = content[:3000]
        
        # Add filename context if available
        if filename:
            content_sample = f"Filename: {filename}\n\n{content_sample}"
        
        hints = self._build_regex_hints(content_sample)
        # Generate prompt
        prompt = self.EXTRACTION_PROMPT_TEMPLATE.format(
            content=content_sample,
            hints=json.dumps(hints, ensure_ascii=True)
        )
        
        # Call LLM
        try:
            response = self.llm_model.generate(prompt)
            
            # Parse JSON response
            # Try to extract JSON from response (in case LLM adds extra text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)
            
            data = json.loads(response)
            
            # Create metadata object
            metadata = ExtractedMetadata(
                doc_type=data.get("doc_type"),
                case_number=data.get("case_number"),
                date=data.get("date"),
                court=data.get("court"),
                parties=data.get("parties", []),
                judge=data.get("judge"),
                attorney=data.get("attorney"),
                confidence=data.get("confidence", 0.7),
                extraction_method="llm"
            )
            
            # Populate entities dict
            metadata.entities = {
                "case_number": [metadata.case_number] if metadata.case_number else [],
                "date": [metadata.date] if metadata.date else [],
                "court": [metadata.court] if metadata.court else [],
                "parties": metadata.parties,
                "judge": [metadata.judge] if metadata.judge else [],
                "attorney": [metadata.attorney] if metadata.attorney else []
            }
            
            logger.debug(f"LLM extracted metadata with confidence {metadata.confidence}")
            return metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"LLM response: {response[:200]}")
            raise
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            raise
    
    def _extract_with_regex(
        self,
        content: str,
        filename: Optional[str] = None
    ) -> ExtractedMetadata:
        """Extract metadata using regex patterns"""
        metadata = ExtractedMetadata(extraction_method="regex")
        
        # Combine filename and content for analysis
        full_text = f"{filename or ''}\n{content}"
        
        # Extract case number
        case_patterns = [
            r'(?:Case|No\.|#|Cause)\s*(?:No\.?)?\s*:?\s*(\d{2,4}[-]?[A-Z]{0,3}[-]?\d{3,7})',
            r'\b(\d{2}[A-Z]{2}\d{5,7})\b',
            r'(?:Docket|File)\s*(?:No\.?)?\s*:?\s*([A-Z0-9-]+)',
        ]
        for pattern in case_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.case_number = match.group(1).strip()
                break
        
        # Extract date
        date_patterns = [
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',
            r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.date = match.group(1).strip()
                break
        
        # Extract court
        court_patterns = [
            r'(?:IN THE\s+)?([A-Z][A-Z\s]+(?:COURT|TRIBUNAL))',
            r'((?:Superior|District|Circuit|Family|Federal|Supreme|Municipal)\s+Court)',
        ]
        for pattern in court_patterns:
            match = re.search(pattern, full_text)
            if match:
                metadata.court = match.group(1).strip()
                break
        
        # Extract parties
        party_pattern = r'([A-Z][A-Z\s]+)\s+(?:v\.|vs\.?|versus)\s+([A-Z][A-Z\s]+)'
        match = re.search(party_pattern, full_text)
        if match:
            metadata.parties = [match.group(1).strip(), match.group(2).strip()]
        
        # Extract judge
        judge_patterns = [
            r'(?:Judge|Hon\.|Honorable)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'(?:JUDGE|HON\.)\s+([A-Z\s]+)',
        ]
        for pattern in judge_patterns:
            match = re.search(pattern, full_text)
            if match:
                metadata.judge = match.group(1).strip()
                break
        
        # Extract attorney
        attorney_patterns = [
            r'(?:Attorney|Counsel|Esq\.?)\s*:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:Esq\.|Attorney|Counsel)',
        ]
        for pattern in attorney_patterns:
            match = re.search(pattern, full_text)
            if match:
                metadata.attorney = match.group(1).strip()
                break
        
        # Detect document type
        metadata.doc_type = self._detect_doc_type(full_text)
        
        # Populate entities dict
        metadata.entities = {
            "case_number": [metadata.case_number] if metadata.case_number else [],
            "date": [metadata.date] if metadata.date else [],
            "court": [metadata.court] if metadata.court else [],
            "parties": metadata.parties,
            "judge": [metadata.judge] if metadata.judge else [],
            "attorney": [metadata.attorney] if metadata.attorney else []
        }
        
        # Calculate confidence based on how many fields were extracted
        fields_found = sum([
            bool(metadata.doc_type),
            bool(metadata.case_number),
            bool(metadata.date),
            bool(metadata.court),
            bool(metadata.parties),
            bool(metadata.judge),
            bool(metadata.attorney)
        ])
        metadata.confidence = min(0.9, fields_found / 7.0 + 0.2)
        
        logger.debug(f"Regex extracted {fields_found}/7 fields with confidence {metadata.confidence}")
        return metadata

    def _build_regex_hints(self, content: str) -> Dict[str, List[str]]:
        """Generate regex-derived hints for LLM prompting."""
        hints: Dict[str, List[str]] = {}
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            matches = set()
            for pattern in patterns:
                try:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        if match.groups():
                            for g in match.groups():
                                if g:
                                    matches.add(g.strip())
                        else:
                            matches.add(match.group(0).strip())
                except Exception:
                    continue
            if matches:
                hints[entity_type] = list(matches)[:5]
        return hints
    
    def _detect_doc_type(self, text: str) -> Optional[str]:
        """Detect document type from content"""
        text_lower = text.lower()
        
        # Document type keywords
        doc_type_keywords = {
            'motion': ['motion to', 'moves the court', 'motion for', 'hereby moves'],
            'order': ['it is ordered', 'court orders', 'hereby ordered', 'order granting', 'order denying'],
            'complaint': ['complaint', 'plaintiff alleges', 'cause of action', 'jurisdiction'],
            'answer': ['answer to', 'defendant answers', 'affirmative defense'],
            'affidavit': ['affidavit', 'sworn statement', 'under penalty of perjury', 'affiant states'],
            'subpoena': ['subpoena', 'commanded to appear', 'produce documents', 'witness'],
            'brief': ['brief in support', 'memorandum of law', 'argument', 'conclusion'],
            'petition': ['petition for', 'petitioner', 'prays the court', 'petitioner requests'],
            'notice': ['notice of', 'hereby notified', 'take notice', 'notice is given'],
            'discovery': ['interrogatories', 'request for production', 'request for admission', 'deposition notice'],
            'deposition': ['deposition of', 'deponent', 'q:', 'a:', 'examination'],
            'judgment': ['judgment', 'judgment is entered', 'judgment for', 'final judgment'],
            'contract': ['agreement', 'contract', 'parties agree', 'terms and conditions'],
        }
        
        scores = {}
        for doc_type, keywords in doc_type_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[doc_type] = score
        
        if scores:
            return max(scores, key=scores.get)
        return None
    
    def _get_cache_key(self, content: str) -> str:
        """Generate cache key from content"""
        import hashlib
        return hashlib.md5(content[:1000].encode()).hexdigest()
    
    def clear_cache(self) -> None:
        """Clear extraction cache"""
        self._cache.clear()
        logger.debug("Extraction cache cleared")
