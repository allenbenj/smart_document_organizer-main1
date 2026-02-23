"""
Jurisdiction & Domain Detector
==============================
Prevents 'Analytical Drift' by grounding analysis in specific legal domains.
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Set

class LegalSystem(Enum):
    US_FEDERAL = "us_federal"
    US_STATE = "us_state"
    EU_CIVIL = "eu_civil"
    UK_COMMON = "uk_common"
    UNKNOWN = "unknown"

class LegalDomain(Enum):
    CRIMINAL = "criminal"
    CIVIL = "civil"
    CONTRACT = "contract"
    REGULATORY = "regulatory"
    FAMILY = "family"
    UNKNOWN = "unknown"

@dataclass
class JurisdictionContext:
    system: LegalSystem
    domain: LegalDomain
    confidence: float
    detected_markers: List[str]

class JurisdictionDetector:
    def __init__(self):
        # Regex triggers for domain detection
        self.us_criminal_triggers = [
            r"\b(defendant|prosecution|indictment|felony|misdemeanor|habeas|4th amendment|5th amendment|miranda)\b",
            r"\bv\.\s+[A-Z][a-z]+",  # Case citation like State v. Smith
            r"\bU\.S\.C\.\b",        # US Code
            r"\bF\.2d\b|\bF\.3d\b",  # Federal Reporter
        ]
        
        self.contract_triggers = [
            r"\b(agreement|party of the first part|breach|consideration|warranty|indemnify)\b",
            r"\bsection\s+\d+(\.\d+)?",
        ]
        
        self.gdpr_triggers = [
            r"\b(gdpr|article 6|data subject|controller|processor|eu 2016/679)\b",
        ]

    def detect(self, text: str) -> JurisdictionContext:
        """
        Scans text for jurisdictional markers to prevent analytical drift.
        """
        text_lower = text.lower()
        
        # 1. Detect System (US vs EU)
        system = LegalSystem.UNKNOWN
        if "u.s." in text_lower or "united states" in text_lower or "$" in text:
            system = LegalSystem.US_FEDERAL
        elif "commonwealth" in text_lower or "state of" in text_lower:
            system = LegalSystem.US_STATE
        elif "eu" in text_lower or "regulation (eu)" in text_lower:
            system = LegalSystem.EU_CIVIL

        # 2. Detect Domain (Criminal vs Civil/Contract)
        domain = LegalDomain.UNKNOWN
        markers = []
        
        # Check Criminal
        crim_score = 0
        for pattern in self.us_criminal_triggers:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                crim_score += len(matches)
                markers.extend(matches[:3]) # Keep first few as evidence
        
        # Check Contract
        contract_score = 0
        for pattern in self.contract_triggers:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                contract_score += len(matches)
                markers.extend(matches[:3])

        # Check Regulatory (GDPR/Compliance)
        reg_score = 0
        for pattern in self.gdpr_triggers:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                reg_score += len(matches)
                markers.extend(matches[:3])

        # Decision Logic
        if reg_score > crim_score and reg_score > contract_score:
            domain = LegalDomain.REGULATORY
            if system == LegalSystem.UNKNOWN: system = LegalSystem.EU_CIVIL # Infer EU for GDPR
        elif crim_score > contract_score:
            domain = LegalDomain.CRIMINAL
        elif contract_score > 0:
            domain = LegalDomain.CONTRACT
        
        confidence = 0.0
        total_hits = crim_score + contract_score + reg_score
        if total_hits > 0:
            confidence = min(1.0, total_hits / 10.0)

        return JurisdictionContext(
            system=system,
            domain=domain,
            confidence=confidence,
            detected_markers=list(set(markers))
        )
