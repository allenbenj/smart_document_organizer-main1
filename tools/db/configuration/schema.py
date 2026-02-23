"""
Configuration schema validation support.

Provides schema definition and validation for configuration values.
"""

from typing import Any, Dict, List, Optional, Type
from enum import Enum


class ValidationError(Exception):
    """Configuration validation error."""
    
    def __init__(self, message: str, key: Optional[str] = None, value: Any = None):
        super().__init__(message)
        self.key = key
        self.value = value
        self.message = message


class SchemaType(str, Enum):
    """Schema data types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    ANY = "any"


class ConfigurationSchema:
    """Configuration schema for validation."""
    
    def __init__(self, schema: Optional[Dict[str, Any]] = None):
        """
        Initialize configuration schema.
        
        Args:
            schema: Schema definition in JSON Schema-like format
        """
        self.schema = schema or {}
        self._compiled = False
    
    def add_field(
        self,
        key: str,
        field_type: SchemaType,
        required: bool = False,
        default: Any = None,
        description: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        pattern: Optional[str] = None,
        choices: Optional[List[Any]] = None
    ) -> 'ConfigurationSchema':
        """
        Add a field to the schema.
        
        Args:
            key: Configuration key (dot-notation supported)
            field_type: Type of the field
            required: Whether field is required
            default: Default value if not provided
            description: Field description
            min_value: Minimum value (for numeric types)
            max_value: Maximum value (for numeric types)
            pattern: Regex pattern (for string types)
            choices: List of valid choices
        
        Returns:
            Self for chaining
        """
        field_spec = {
            "type": field_type.value,
            "required": required,
        }
        
        if default is not None:
            field_spec["default"] = default
        if description:
            field_spec["description"] = description
        if min_value is not None:
            field_spec["minimum"] = min_value
        if max_value is not None:
            field_spec["maximum"] = max_value
        if pattern:
            field_spec["pattern"] = pattern
        if choices:
            field_spec["enum"] = choices
        
        self.schema[key] = field_spec
        return self
    
    def validate(self, config: Dict[str, Any]) -> bool:
        """
        Validate configuration against schema.
        
        Args:
            config: Configuration to validate
        
        Returns:
            True if valid
        
        Raises:
            ValidationError: If validation fails
        """
        for key, spec in self.schema.items():
            value = self._get_nested_value(config, key)
            
            # Check required fields
            if spec.get("required", False) and value is None:
                raise ValidationError(
                    f"Required configuration key '{key}' is missing",
                    key=key
                )
            
            # Skip validation if value is None and not required
            if value is None:
                continue
            
            # Type validation
            expected_type = spec.get("type", "any")
            if not self._check_type(value, expected_type):
                raise ValidationError(
                    f"Configuration key '{key}' has invalid type. "
                    f"Expected {expected_type}, got {type(value).__name__}",
                    key=key,
                    value=value
                )
            
            # Range validation for numeric types
            if expected_type in ("integer", "float"):
                if "minimum" in spec and value < spec["minimum"]:
                    raise ValidationError(
                        f"Configuration key '{key}' value {value} is below minimum {spec['minimum']}",
                        key=key,
                        value=value
                    )
                if "maximum" in spec and value > spec["maximum"]:
                    raise ValidationError(
                        f"Configuration key '{key}' value {value} exceeds maximum {spec['maximum']}",
                        key=key,
                        value=value
                    )
            
            # Pattern validation for strings
            if expected_type == "string" and "pattern" in spec:
                import re
                if not re.match(spec["pattern"], value):
                    raise ValidationError(
                        f"Configuration key '{key}' value '{value}' does not match pattern '{spec['pattern']}'",
                        key=key,
                        value=value
                    )
            
            # Enum validation
            if "enum" in spec and value not in spec["enum"]:
                raise ValidationError(
                    f"Configuration key '{key}' value '{value}' is not in allowed choices: {spec['enum']}",
                    key=key,
                    value=value
                )
        
        return True
    
    def get_defaults(self) -> Dict[str, Any]:
        """
        Get default values from schema.
        
        Returns:
            Dictionary of default values
        """
        defaults = {}
        for key, spec in self.schema.items():
            if "default" in spec:
                self._set_nested_value(defaults, key, spec["default"])
        return defaults
    
    @staticmethod
    def _get_nested_value(data: Dict[str, Any], key: str) -> Any:
        """Get nested value using dot notation."""
        keys = key.split(".")
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value
    
    @staticmethod
    def _set_nested_value(data: Dict[str, Any], key: str, value: Any) -> None:
        """Set nested value using dot notation."""
        keys = key.split(".")
        current = data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
    
    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        if expected_type == "any":
            return True
        
        type_map = {
            "string": str,
            "integer": int,
            "float": (int, float),
            "boolean": bool,
            "array": (list, tuple),
            "object": dict,
        }
        
        expected_python_type = type_map.get(expected_type)
        if expected_python_type is None:
            return False
        
        return isinstance(value, expected_python_type)


__all__ = ["ConfigurationSchema", "ValidationError", "SchemaType"]
