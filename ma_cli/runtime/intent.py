"""
Intent Analysis Module

Analyzes user requests to determine intent, required tools, and complexity.
"""

import re
from typing import Any

from ..models.intent import Intent, IntentType, TaskComplexity


class IntentAnalyzer:
    """Analyzes user requests to extract structured intent."""

    # Keywords mapping to intent types
    INTENT_KEYWORDS = {
        IntentType.CREATE: ["create", "make", "generate", "write", "build", "add", "new"],
        IntentType.MODIFY: ["modify", "change", "update", "edit", "fix", "refactor", "improve"],
        IntentType.DELETE: ["delete", "remove", "drop", "clear"],
        IntentType.READ: ["read", "show", "list", "display", "view", "check", "inspect"],
        IntentType.TEST: ["test", "verify", "validate", "run tests", "execute tests"],
        IntentType.EXPLAIN: ["explain", "describe", "analyze", "understand", "what"],
        IntentType.COMPLEX: ["implement", "develop", "complete", "finish", "solve"],
    }

    COMPLEXITY_INDICATORS = {
        TaskComplexity.SIMPLE: ["single", "simple", "quick", "basic"],
        TaskComplexity.MEDIUM: ["multiple", "several", "moderate"],
        TaskComplexity.COMPLEX: [
            "complex",
            "advanced",
            "full",
            "complete",
            "end-to-end",
            "pipeline",
        ],
    }

    def __init__(self):
        self._patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict[str, list[re.Pattern]]:
        """Compile regex patterns for intent detection."""
        patterns = {}
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            patterns[intent_type] = [
                re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in keywords
            ]
        return patterns

    def analyze(self, request: str, context: dict[str, Any] | None = None) -> Intent:
        """
        Analyze a user request and return structured intent.

        Args:
            request: The user's natural language request
            context: Optional context about current state

        Returns:
            Intent object with parsed details
        """
        if not request or not request.strip():
            raise ValueError("Request cannot be empty")

        request_lower = request.lower()
        detected_intents = []
        detected_complexity = TaskComplexity.MEDIUM  # Default

        # Detect Intent Type
        max_score = 0
        primary_intent = IntentType.COMPLEX

        for intent_type, patterns in self._patterns.items():
            score = 0
            for pattern in patterns:
                matches = pattern.findall(request)
                score += len(matches)

            if score > max_score:
                max_score = score
                primary_intent = intent_type
            elif score > 0:
                detected_intents.append(intent_type)

        # Detect Complexity
        for complexity, indicators in self.COMPLEXITY_INDICATORS.items():
            if any(ind in request_lower for ind in indicators):
                detected_complexity = complexity
                break

        # Extract potential entities (files, modules, etc.)
        entities = self._extract_entities(request)

        # Determine if multi-step is required
        requires_planning = (
            primary_intent in [IntentType.COMPLEX, IntentType.CREATE, IntentType.MODIFY]
            or detected_complexity == TaskComplexity.COMPLEX
            or len(entities) > 1
        )

        return Intent(
            type=primary_intent,
            description=request.strip(),
            complexity=detected_complexity,
            entities=entities,
            requires_planning=requires_planning,
            confidence=min(1.0, max_score / 3.0),  # Normalize confidence
        )

    def _extract_entities(self, request: str) -> list[dict[str, str]]:
        """Extract potential entities like filenames, classes, functions."""
        entities = []

        # File patterns
        file_pattern = r"[\w\-\.]+\.(py|js|ts|md|txt|json|yaml|yml|cfg|ini)"
        for match in re.finditer(file_pattern, request):
            entities.append({"type": "file", "value": match.group()})

        # Function patterns (simple heuristic)
        func_pattern = r"(\w+)\s*\("
        for match in re.finditer(func_pattern, request):
            func_name = match.group(1)
            if func_name not in ["if", "for", "while", "print", "return", "def"]:
                entities.append({"type": "function", "value": func_name})

        return entities
