"""
Unified Toulmin Model Analyzer (Pattern + LLM + Feedback)
- High-performance argument structure analysis
- Agent-style feedback adaptation
- Async, batch, and pipeline ready
"""

import asyncio
import json
import logging
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

def try_import(path):
    try:
        return __import__(path, fromlist=['*'])
    except ImportError:
        return None

LLMManager = try_import('core.llm_providers').LLMManager if try_import('core.llm_providers') else None
LLMProviderEnum = try_import('core.llm_providers').LLMProviderEnum if try_import('core.llm_providers') else None
TaskComplexity = try_import('core.model_switcher').TaskComplexity if try_import('core.model_switcher') else None

@dataclass
class ToulminConfig:
    min_confidence: float = 0.6
    max_arguments: int = 15
    enable_pattern_matching: bool = True
    use_llm_enhancement: bool = True
    # Agent feedback adaptation params
    pattern_tweaks: Dict[str, Any] = field(default_factory=dict)
    prompt_tuning: Dict[str, str] = field(default_factory=dict)
    def update_from_feedback(self, feedback: List[Dict[str, Any]]):
        """Agent-style feedback adjustment"""
        for fb in feedback:
            if fb.get("type") == "missing_components":
                self.prompt_tuning["completeness"] = "*Do not omit any Toulmin component*"
            elif fb.get("type") == "incorrect_component_classification":
                self.prompt_tuning["precision"] = "*Be precise in assigning each sentence to its correct component*"
            elif fb.get("type") == "raise_min_confidence":
                self.min_confidence = min(0.99, self.min_confidence + 0.05)
            elif fb.get("type") == "lower_min_confidence":
                self.min_confidence = max(0.5, self.min_confidence - 0.05)

class ToulminAnalyzer:
    """
    Unified Toulmin Model analyzer for legal argument structure identification.
    """
    def __init__(self, llm_manager: Optional[Any], config: ToulminConfig):
        self.llm_manager = llm_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.toulmin_patterns = {
            "claims": [
                r"(?i)\b(?:argue|contend|assert|claim|maintain|submit|position)\b",
                r"(?i)\b(?:we conclude|the court concludes|holds?|finding)\b",
                r"(?i)^Claim:\s*.*$"
            ],
            "data": [
                r"(?i)\b(?:evidence|fact|exhibit|testimony|witness|document|record)\b",
                r"(?i)\b(?:shows?|demonstrates?|proves?|establishes?|indicates?)\b",
                r"(?i)^Data:\s*.*$"
            ],
            "warrants": [
                r"(?i)\b(?:because|since|as|for|given that|whereas)\b",
                r"(?i)\b(?:rule|law|principle|standard|precedent)\b",
                r"(?i)^Warrant:\s*.*$"
            ],
            "backing": [
                r"(?i)\b(?:support|authority|according to|based on|pursuant to)\b",
                r"(?i)\b(?:precedent|case law|statute|regulation)\b",
                r"(?i)^Backing:\s*.*$"
            ],
            "rebuttals": [
                r"(?i)\b(?:however|but|nevertheless|although|despite|except|unless)\b",
                r"(?i)\b(?:counter|rebut|refute|dispute|challenge|object)\b",
                r"(?i)^Rebuttal:\s*.*$"
            ],
            "qualifiers": [
                r"(?i)\b(?:probably|possibly|likely|perhaps|maybe|might|may|could)\b",
                r"(?i)\b(?:arguably|presumably|seemingly|apparently|evidently)\b",
                r"(?i)^Qualifier:\s*.*$"
            ]
        }
        self.default_prompt = """
        Analyze the legal argument structure using Toulmin Model. Identify:
        Claims: Assertions, conclusions, positions being argued
        Data: Facts, evidence, grounds supporting claims
        Warrants: Rules, principles connecting data to claims
        Backing: Authority, precedent supporting warrants
        Rebuttals: Exceptions, counterarguments, limitations
        Qualifiers: Degree of certainty, modal expressions
        Document: {document}
        Initial Components: {components}
        {completeness}{precision}
        Return JSON: {{"claims": [...], "data": [...], "warrants": [...], "backing": [...], "rebuttals": [...], "qualifiers": []}}
        Each component: {{"text": "...", "confidence": 0.8, "type": "...", "relationship": "..."}}
        """

    def apply_feedback(self, feedback: List[Dict[str, Any]]):
        self.config.update_from_feedback(feedback)

    async def analyze_async(self, document_content: str, context: Dict[str, Any] = None, feedback: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        if context is None:
            context = {}
        if feedback:
            self.apply_feedback(feedback)
        try:
            pattern_components = self._extract_with_patterns(document_content)
            enhanced_components = pattern_components
            if self.config.use_llm_enhancement and self.llm_manager:
                enhanced_components = await self._enhance_with_llm(document_content, pattern_components, context)
            argument_structures = self._build_argument_structures(enhanced_components)
            confidence = self._calculate_confidence(enhanced_components)
            return {
                "components": enhanced_components,
                "argument_structures": argument_structures,
                "confidence": confidence,
                "toulmin_completeness": self._assess_completeness(enhanced_components),
                "model_used": "pattern+llm" if self.config.use_llm_enhancement else "pattern"
            }
        except Exception as e:
            self.logger.error(f"Toulmin analysis failed: {str(e)}")
            return {"error": str(e), "confidence": 0.0}

    def _extract_with_patterns(self, document_content: str) -> Dict[str, List[Dict[str, Any]]]:
        paragraphs = document_content.split("\n\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        components = {k: [] for k in self.toulmin_patterns.keys()}
        for i, paragraph in enumerate(paragraphs):
            for component_type, patterns in self.toulmin_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, paragraph):
                        strength = sum(1 for p in patterns if re.search(p, paragraph))
                        confidence = min(0.9, 0.5 + (strength * 0.1))
                        components[component_type].append({
                            "text": paragraph,
                            "confidence": confidence,
                            "paragraph_index": i,
                            "type": self._classify_component_type(paragraph, component_type),
                            "pattern_matched": pattern
                        })
                        break
        return components

    def _classify_component_type(self, text: str, component_category: str) -> str:
        text_lower = text.lower()
        if component_category == "claims":
            if any(word in text_lower for word in ["conclude", "hold", "find"]):
                return "conclusion"
            elif any(word in text_lower for word in ["argue", "contend", "assert"]):
                return "assertion"
            else:
                return "position"
        elif component_category == "data":
            if any(word in text_lower for word in ["evidence", "testimony", "exhibit"]):
                return "evidence"
            elif any(word in text_lower for word in ["fact", "circumstance"]):
                return "fact"
            else:
                return "grounds"
        elif component_category == "warrants":
            if any(word in text_lower for word in ["rule", "law", "statute"]):
                return "legal_rule"
            elif any(word in text_lower for word in ["principle", "standard"]):
                return "principle"
            else:
                return "inference"
        return "general"

    async def _enhance_with_llm(self, document_content: str, pattern_components: Dict[str, List[Dict[str, Any]]], context: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        try:
            trimmed_content = document_content[:3500] + "..." if len(document_content) > 3500 else document_content
            completeness = self.config.prompt_tuning.get("completeness", "")
            precision = self.config.prompt_tuning.get("precision", "")
            prompt = self.default_prompt.format(
                document=trimmed_content,
                components=json.dumps(pattern_components, indent=2),
                completeness=completeness,
                precision=precision
            )
            complexity = context.get("complexity", TaskComplexity.MODERATE if TaskComplexity else "moderate")
            model_config = self._get_model_for_complexity(complexity)
            response = await self.llm_manager.complete(
                prompt=prompt,
                model=model_config["model"],
                provider=model_config["provider"],
                temperature=0.2,
                max_tokens=2500
            )
            llm_components = self._parse_llm_response(response.content)
            return self._merge_components(pattern_components, llm_components)
        except Exception as e:
            self.logger.warning(f"LLM enhancement failed, using pattern results: {str(e)}")
            return pattern_components

    def _parse_llm_response(self, response_content: str) -> Dict[str, List[Dict[str, Any]]]:
        try:
            if "```json" in response_content:
                json_content = response_content.split("```json")[1].split("```")[0]
            elif "```" in response_content:
                json_content = response_content.split("```")[1].split("```")[0]
            else:
                json_content = response_content
            parsed_data = json.loads(json_content.strip())
            validated_components = {}
            component_types = list(self.toulmin_patterns.keys())
            for comp_type in component_types:
                components = parsed_data.get(comp_type, [])
                if isinstance(components, list):
                    validated_components[comp_type] = [comp for comp in components if isinstance(comp, dict) and comp.get("confidence", 0) >= self.config.min_confidence]
                else:
                    validated_components[comp_type] = []
            return validated_components
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"Failed to parse LLM response: {str(e)}")
            return {comp_type: [] for comp_type in self.toulmin_patterns.keys()}

    def _merge_components(self, pattern_components: Dict[str, List[Dict[str, Any]]], llm_components: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        merged = {}
        for comp_type in self.toulmin_patterns.keys():
            pattern_comps = pattern_components.get(comp_type, [])
            llm_comps = llm_components.get(comp_type, [])
            high_conf_llm = [c for c in llm_comps if c.get("confidence", 0) >= 0.8]
            unique_pattern = []
            for pc in pattern_comps:
                if not any(self._text_similarity(pc["text"], lc["text"]) > 0.6 for lc in high_conf_llm):
                    unique_pattern.append(pc)
            merged[comp_type] = (high_conf_llm + unique_pattern)[:self.config.max_arguments]
        return merged

    def _text_similarity(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        return intersection / union if union > 0 else 0.0

    def _build_argument_structures(self, components: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        structures = []
        claims = components.get("claims", [])
        for i, claim in enumerate(claims):
            claim_index = claim.get("paragraph_index", i)
            closest_data = self._find_closest_component(claim_index, components.get("data", []))
            closest_warrant = self._find_closest_component(claim_index, components.get("warrants", []))
            closest_backing = self._find_closest_component(claim_index, components.get("backing", [])) if closest_warrant else None
            closest_rebuttal = self._find_closest_component(claim_index, components.get("rebuttals", []))
            closest_qualifier = self._find_closest_component(claim_index, components.get("qualifiers", []))
            structure_components = [claim, closest_data, closest_warrant]
            completeness = sum(1 for comp in structure_components if comp) / 3
            if closest_backing:
                completeness += 0.1
            if closest_rebuttal:
                completeness += 0.1
            if closest_qualifier:
                completeness += 0.1
            structure = {
                "id": f"argument_{i+1}",
                "claim": claim,
                "data": closest_data,
                "warrant": closest_warrant,
                "backing": closest_backing,
                "rebuttal": closest_rebuttal,
                "qualifier": closest_qualifier,
                "completeness": min(1.0, completeness),
                "strength": self._assess_argument_strength(claim, closest_data, closest_warrant, closest_backing)
            }
            structures.append(structure)
        return structures

    def _find_closest_component(self, reference_index: int, components: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not components:
            return None
        closest = None
        min_distance = float('inf')
        for comp in components:
            comp_index = comp.get("paragraph_index", 0)
            distance = abs(comp_index - reference_index)
            if distance < min_distance:
                min_distance = distance
                closest = comp
        return closest

    def _assess_argument_strength(self, claim: Dict[str, Any], data: Optional[Dict[str, Any]], warrant: Optional[Dict[str, Any]], backing: Optional[Dict[str, Any]]) -> float:
        strength = 0.0
        if claim:
            strength += claim.get("confidence", 0) * 0.4
        if data:
            strength += data.get("confidence", 0) * 0.3
        if warrant:
            strength += warrant.get("confidence", 0) * 0.2
        if backing:
            strength += backing.get("confidence", 0) * 0.1
        return min(1.0, strength)

    def _calculate_confidence(self, components: Dict[str, List[Dict[str, Any]]]) -> float:
        all_confidences = []
        for comp_type, comp_list in components.items():
            for comp in comp_list:
                conf = comp.get("confidence", 0)
                if isinstance(conf, (int, float)):
                    all_confidences.append(conf)
        if not all_confidences:
            return 0.0
        diversity_bonus = len([k for k, v in components.items() if v]) / 6 * 0.1
        return min(1.0, sum(all_confidences) / len(all_confidences) + diversity_bonus)

    def _assess_completeness(self, components: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        component_counts = {k: len(v) for k, v in components.items()}
        total_components = sum(component_counts.values())
        essential_present = sum(1 for comp in ["claims", "data", "warrants"] if component_counts[comp] > 0)
        essential_completeness = essential_present / 3
        full_completeness = sum(1 for count in component_counts.values() if count > 0) / 6
        return {
            "essential_completeness": essential_completeness,
            "full_completeness": full_completeness,
            "component_counts": component_counts,
            "total_components": total_components,
            "has_complete_arguments": essential_completeness >= 1.0
        }

    def _get_model_for_complexity(self, complexity: Any) -> Dict[str, Any]:
        if not LLMProviderEnum:
            return {"model": "gpt-5-nano-2025-08-07", "provider": "openai"}
        if complexity == getattr(TaskComplexity, 'SIMPLE', 'simple'):
            return {"model": "gpt-5-nano-2025-08-07", "provider": LLMProviderEnum.OPENAI}
        elif complexity == getattr(TaskComplexity, 'COMPLEX', 'complex'):
            return {"model": "gpt-5-nano-2025-08-07", "provider": LLMProviderEnum.OPENAI}
        else:
            return {"model": "gpt-5-nano-2025-08-07", "provider": LLMProviderEnum.OPENAI}
