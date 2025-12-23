"""
Custom Rules Engine
====================

Allows users to define custom file organization rules.
Rules are evaluated before AI classification for priority handling.
"""

import re
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import json

from src.config.categories import FileCategory
from src.classification.tier1_metadata import ClassificationResult
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class MatchType(Enum):
    """Types of pattern matching."""
    CONTAINS = "contains"        # Filename contains text
    STARTS_WITH = "starts_with"  # Filename starts with text
    ENDS_WITH = "ends_with"      # Filename ends with text
    REGEX = "regex"              # Regular expression match
    EXTENSION = "extension"      # File extension match
    SIZE_GT = "size_gt"          # Size greater than (bytes)
    SIZE_LT = "size_lt"          # Size less than (bytes)


@dataclass
class CustomRule:
    """A custom file organization rule.
    
    Attributes:
        id: Unique identifier.
        name: Human-readable rule name.
        enabled: Whether rule is active.
        priority: Higher = evaluated first (1-100).
        match_type: Type of pattern matching.
        pattern: The pattern to match.
        category: Target category for matching files.
        subcategory: Target subcategory.
        is_sensitive: Mark as sensitive.
        destination_folder: Custom destination folder (overrides category).
    """
    id: int
    name: str
    enabled: bool = True
    priority: int = 50
    match_type: MatchType = MatchType.CONTAINS
    pattern: str = ""
    category: str = "Documents"
    subcategory: str = ""
    is_sensitive: bool = False
    destination_folder: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        data['match_type'] = self.match_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'CustomRule':
        """Create from dictionary."""
        data = data.copy()
        data['match_type'] = MatchType(data.get('match_type', 'contains'))
        return cls(**data)

    def matches(self, file_path: Path) -> bool:
        """Check if a file matches this rule.
        
        Args:
            file_path: Path to check.
        
        Returns:
            True if file matches rule.
        """
        if not self.enabled:
            return False

        filename = file_path.name.lower()
        pattern_lower = self.pattern.lower()

        try:
            if self.match_type == MatchType.CONTAINS:
                return pattern_lower in filename

            elif self.match_type == MatchType.STARTS_WITH:
                return filename.startswith(pattern_lower)

            elif self.match_type == MatchType.ENDS_WITH:
                return filename.endswith(pattern_lower)

            elif self.match_type == MatchType.REGEX:
                return bool(re.search(self.pattern, filename, re.IGNORECASE))

            elif self.match_type == MatchType.EXTENSION:
                ext = file_path.suffix.lower().lstrip('.')
                return ext == pattern_lower.lstrip('.')

            elif self.match_type == MatchType.SIZE_GT:
                return file_path.stat().st_size > int(self.pattern)

            elif self.match_type == MatchType.SIZE_LT:
                return file_path.stat().st_size < int(self.pattern)

        except Exception as e:
            logger.debug(f"Rule match error: {e}")
            return False

        return False


class RulesEngine:
    """Engine for evaluating custom file organization rules.
    
    Rules are stored in a JSON file and evaluated in priority order.
    """

    DEFAULT_RULES_FILE = "custom_rules.json"

    def __init__(
        self,
        rules_file: Optional[Path] = None,
        base_directory: Optional[Path] = None
    ):
        """Initialize rules engine.
        
        Args:
            rules_file: Path to rules JSON file.
            base_directory: Base directory for config.
        """
        self.base_directory = base_directory or Path.home() / "Organized"
        self.rules_file = rules_file or self.base_directory / self.DEFAULT_RULES_FILE
        self._rules: List[CustomRule] = []
        self._next_id = 1
        self._load_rules()

        # Add default rules if none exist
        if not self._rules:
            self._add_default_rules()

    def _load_rules(self) -> None:
        """Load rules from file."""
        if self.rules_file.exists():
            try:
                with open(self.rules_file, 'r') as f:
                    data = json.load(f)
                    self._rules = [
                        CustomRule.from_dict(rule)
                        for rule in data.get('rules', [])
                    ]
                    self._next_id = data.get('next_id', 1)
                logger.debug(f"Loaded {len(self._rules)} custom rules")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error loading rules: {e}")
                self._rules = []

    def _save_rules(self) -> None:
        """Save rules to file."""
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'next_id': self._next_id,
            'rules': [rule.to_dict() for rule in self._rules]
        }

        with open(self.rules_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _add_default_rules(self) -> None:
        """Add useful default rules."""
        defaults = [
            CustomRule(
                id=self._next_id,
                name="Invoices to Finance",
                pattern="invoice",
                match_type=MatchType.CONTAINS,
                category="Documents",
                subcategory="Finance/Invoices",
                priority=80
            ),
            CustomRule(
                id=self._next_id + 1,
                name="Receipts to Finance",
                pattern="receipt",
                match_type=MatchType.CONTAINS,
                category="Documents",
                subcategory="Finance/Receipts",
                priority=80
            ),
            CustomRule(
                id=self._next_id + 2,
                name="Screenshots folder",
                pattern="screenshot",
                match_type=MatchType.CONTAINS,
                category="Images",
                subcategory="Screenshots",
                priority=70
            ),
            CustomRule(
                id=self._next_id + 3,
                name="Resume/CV files",
                pattern="resume|cv|curriculum",
                match_type=MatchType.REGEX,
                category="Documents",
                subcategory="Personal/Resume",
                is_sensitive=True,
                priority=90
            ),
            CustomRule(
                id=self._next_id + 4,
                name="Tax documents",
                pattern="tax|1099|w2|w-2",
                match_type=MatchType.REGEX,
                category="Documents",
                subcategory="Finance/Tax",
                is_sensitive=True,
                priority=95
            ),
        ]

        self._rules = defaults
        self._next_id = len(defaults) + 1
        self._save_rules()
        logger.info(f"Created {len(defaults)} default rules")

    def evaluate(self, file_path: Path) -> Optional[ClassificationResult]:
        """Evaluate a file against all rules.
        
        Args:
            file_path: Path to file.
        
        Returns:
            ClassificationResult if a rule matches, None otherwise.
        """
        file_path = Path(file_path)

        # Sort by priority (highest first)
        sorted_rules = sorted(
            self._rules,
            key=lambda r: r.priority,
            reverse=True
        )

        for rule in sorted_rules:
            if rule.matches(file_path):
                logger.info(f"Rule matched: '{rule.name}' for {file_path.name}")

                return ClassificationResult(
                    category=FileCategory.DOCUMENTS,  # Default, will use subcategory
                    subcategory=f"{rule.category}/{rule.subcategory}" if rule.subcategory else rule.category,
                    confidence=1.0,
                    classification_tier=0,  # Custom rule (before tier 1)
                    is_sensitive=rule.is_sensitive,
                    needs_deeper_analysis=False,
                    metadata={
                        'matched_rule': rule.name,
                        'rule_id': rule.id,
                    },
                    suggested_folder=rule.destination_folder or f"{rule.category}/{rule.subcategory or 'General'}"
                )

        return None

    def add_rule(
        self,
        name: str,
        pattern: str,
        category: str,
        subcategory: str = "",
        match_type: MatchType = MatchType.CONTAINS,
        priority: int = 50,
        is_sensitive: bool = False
    ) -> CustomRule:
        """Add a new custom rule.
        
        Args:
            name: Human-readable name.
            pattern: Pattern to match.
            category: Target category.
            subcategory: Target subcategory.
            match_type: Type of matching.
            priority: Rule priority (1-100).
            is_sensitive: Mark as sensitive.
        
        Returns:
            The created rule.
        """
        rule = CustomRule(
            id=self._next_id,
            name=name,
            pattern=pattern,
            category=category,
            subcategory=subcategory,
            match_type=match_type,
            priority=priority,
            is_sensitive=is_sensitive
        )

        self._next_id += 1
        self._rules.append(rule)
        self._save_rules()

        logger.info(f"Added rule: {name}")
        return rule

    def remove_rule(self, rule_id: int) -> bool:
        """Remove a rule by ID.
        
        Args:
            rule_id: ID of rule to remove.
        
        Returns:
            True if removed.
        """
        for i, rule in enumerate(self._rules):
            if rule.id == rule_id:
                removed = self._rules.pop(i)
                self._save_rules()
                logger.info(f"Removed rule: {removed.name}")
                return True
        return False

    def enable_rule(self, rule_id: int, enabled: bool = True) -> bool:
        """Enable or disable a rule.
        
        Args:
            rule_id: ID of rule.
            enabled: Whether to enable.
        
        Returns:
            True if found and updated.
        """
        for rule in self._rules:
            if rule.id == rule_id:
                rule.enabled = enabled
                self._save_rules()
                return True
        return False

    def get_rules(self) -> List[CustomRule]:
        """Get all rules.
        
        Returns:
            List of all rules.
        """
        return self._rules.copy()

    def get_rule(self, rule_id: int) -> Optional[CustomRule]:
        """Get a rule by ID.
        
        Args:
            rule_id: ID to find.
        
        Returns:
            The rule or None.
        """
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None

    def update_rule(self, rule_id: int, **kwargs) -> Optional[CustomRule]:
        """Update a rule's properties.
        
        Args:
            rule_id: ID of rule to update.
            **kwargs: Properties to update.
        
        Returns:
            Updated rule or None.
        """
        for rule in self._rules:
            if rule.id == rule_id:
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                self._save_rules()
                return rule
        return None
