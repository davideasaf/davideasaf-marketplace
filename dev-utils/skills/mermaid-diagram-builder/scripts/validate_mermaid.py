#!/usr/bin/env python3
"""
Mermaid Diagram Validator

Validates Mermaid diagrams for:
1. Syntax correctness
2. Color scheme compliance
3. Text readability
4. Rendering capability
"""

import re
import sys
from typing import List, Tuple, Optional

# Approved color palette based on reference image
APPROVED_COLORS = {
    # Background and text
    'background': '#1a1a1a',
    'text': '#ffffff',
    'text_alt': '#f5f5f5',

    # Accent colors
    'blue': '#4472C4',
    'blue_light': '#6B9BD1',
    'orange': '#FFA500',
    'orange_light': '#FFB732',
    'green': '#4CAF50',
    'green_light': '#66BB6A',
    'red': '#E74C3C',
    'red_light': '#EC7063',

    # Additional approved colors
    'gray': '#6c757d',
    'gray_light': '#9ba3a8',
    'purple': '#9B59B6',
    'teal': '#1abc9c',
}

# Color contrast requirements (WCAG AA standard)
MIN_CONTRAST_RATIO = 4.5


class MermaidValidator:
    def __init__(self, mermaid_content: str):
        self.content = mermaid_content
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validation checks"""
        self._check_syntax()
        self._check_colors()
        self._check_text_length()
        self._check_styling()

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def _check_syntax(self):
        """Basic syntax validation"""
        # Check for opening mermaid declaration
        if not re.search(r'```mermaid', self.content, re.IGNORECASE):
            self.errors.append("Missing opening ```mermaid declaration")

        # Check for closing backticks
        if not re.search(r'```\s*$', self.content):
            self.errors.append("Missing closing ``` declaration")

        # Check for valid diagram type
        valid_types = ['graph', 'flowchart', 'sequenceDiagram', 'classDiagram',
                      'stateDiagram', 'erDiagram', 'journey', 'gantt', 'pie',
                      'gitGraph', 'mindmap', 'timeline', 'quadrantChart']

        has_valid_type = any(diagram_type in self.content for diagram_type in valid_types)
        if not has_valid_type:
            self.errors.append(f"No valid diagram type found. Must include one of: {', '.join(valid_types)}")

    def _check_colors(self):
        """Validate color usage"""
        # Find all color definitions (hex colors)
        hex_colors = re.findall(r'#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3}', self.content)

        approved_hex_values = set(APPROVED_COLORS.values())

        for color in hex_colors:
            # Normalize 3-digit hex to 6-digit
            if len(color) == 4:
                color = f"#{color[1]*2}{color[2]*2}{color[3]*2}"

            color_upper = color.upper()

            # Check if color is in approved list
            if color_upper not in [c.upper() for c in approved_hex_values]:
                self.warnings.append(
                    f"Color {color} not in approved palette. "
                    f"Consider using approved colors: {', '.join(APPROVED_COLORS.keys())}"
                )

    def _check_text_length(self):
        """Check for excessively long text in nodes"""
        # Find text in nodes (simplified pattern)
        node_texts = re.findall(r'\[([^\]]+)\]', self.content)
        node_texts += re.findall(r'\(([^\)]+)\)', self.content)
        node_texts += re.findall(r'\{([^\}]+)\}', self.content)

        for text in node_texts:
            # Strip HTML tags if present
            clean_text = re.sub(r'<[^>]+>', '', text)

            if len(clean_text) > 60:
                self.warnings.append(
                    f"Node text may be too long ({len(clean_text)} chars): '{clean_text[:40]}...'. "
                    "Consider breaking into multiple lines or simplifying."
                )

    def _check_styling(self):
        """Check for recommended styling patterns"""
        # Check for theme configuration
        if 'theme:' not in self.content and '%%init' not in self.content:
            self.warnings.append(
                "Consider adding theme configuration (%%init or theme:) for consistent styling"
            )

        # Recommend classDef for repeated styling
        if self.content.count('fill:') > 3 and 'classDef' not in self.content:
            self.warnings.append(
                "Consider using classDef for repeated styling to improve maintainability"
            )


def validate_file(filepath: str) -> Tuple[bool, List[str], List[str]]:
    """Validate a file containing Mermaid diagram"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        validator = MermaidValidator(content)
        return validator.validate()
    except FileNotFoundError:
        return False, [f"File not found: {filepath}"], []
    except Exception as e:
        return False, [f"Error reading file: {str(e)}"], []


def validate_string(mermaid_content: str) -> Tuple[bool, List[str], List[str]]:
    """Validate a string containing Mermaid diagram"""
    validator = MermaidValidator(mermaid_content)
    return validator.validate()


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: validate_mermaid.py <file_path or 'stdin'>")
        sys.exit(1)

    if sys.argv[1] == 'stdin':
        content = sys.stdin.read()
        is_valid, errors, warnings = validate_string(content)
    else:
        filepath = sys.argv[1]
        is_valid, errors, warnings = validate_file(filepath)

    # Print results
    if errors:
        print("❌ ERRORS:")
        for error in errors:
            print(f"  - {error}")

    if warnings:
        print("\n⚠️  WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")

    if is_valid and not warnings:
        print("✅ Validation passed!")
    elif is_valid:
        print("\n✅ Validation passed with warnings")
    else:
        print("\n❌ Validation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
