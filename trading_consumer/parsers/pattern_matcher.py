"""
Pattern matcher utility for signal parsing.
"""

import re
from typing import List, Dict, Optional, Pattern
from loguru import logger


class PatternMatcher:
    """Utility class for pattern matching in trading signals."""
    
    def __init__(self):
        """Initialize pattern matcher."""
        self._compiled_patterns: Dict[str, Pattern] = {}
        
    def compile_pattern(self, name: str, pattern: str) -> Pattern:
        """Compile and cache a regex pattern."""
        if name not in self._compiled_patterns:
            try:
                self._compiled_patterns[name] = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                logger.error(f"Failed to compile pattern '{name}': {e}")
                raise
        
        return self._compiled_patterns[name]
    
    def find_matches(self, text: str, patterns: List[str]) -> List[str]:
        """Find all matches for given patterns in text."""
        matches = []
        
        for pattern in patterns:
            try:
                compiled_pattern = re.compile(pattern, re.IGNORECASE)
                found_matches = compiled_pattern.findall(text)
                matches.extend(found_matches)
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")
                continue
        
        return matches
    
    def find_first_match(self, text: str, patterns: List[str]) -> Optional[str]:
        """Find the first match for given patterns in text."""
        for pattern in patterns:
            try:
                compiled_pattern = re.compile(pattern, re.IGNORECASE)
                match = compiled_pattern.search(text)
                if match:
                    return match.group(1) if match.groups() else match.group(0)
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")
                continue
        
        return None
    
    def extract_numbers(self, text: str) -> List[float]:
        """Extract all numbers from text."""
        number_pattern = r'\d+(?:\.\d+)?'
        matches = re.findall(number_pattern, text)
        
        numbers = []
        for match in matches:
            try:
                numbers.append(float(match))
            except ValueError:
                continue
        
        return numbers
    
    def extract_currency_amounts(self, text: str) -> List[float]:
        """Extract currency amounts from text (e.g., $100, 50 USD)."""
        currency_patterns = [
            r'\$(\d+(?:\.\d+)?)',  # $100.50
            r'(\d+(?:\.\d+)?)\s*(?:usd|USDC|dollars?)',  # 100 USD
            r'(\d+(?:\.\d+)?)\s*\$',  # 100$
        ]
        
        amounts = []
        for pattern in currency_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    amounts.append(float(match))
                except ValueError:
                    continue
        
        return amounts
    
    def extract_percentages(self, text: str) -> List[float]:
        """Extract percentages from text."""
        percentage_pattern = r'(\d+(?:\.\d+)?)\s*%'
        matches = re.findall(percentage_pattern, text)
        
        percentages = []
        for match in matches:
            try:
                percentages.append(float(match))
            except ValueError:
                continue
        
        return percentages
    
    def has_bullish_indicators(self, text: str) -> bool:
        """Check if text contains bullish indicators."""
        bullish_patterns = [
            r'\bbull(?:ish)?\b',
            r'\bup(?:ward)?\b',
            r'\brise\b',
            r'\bpump\b',
            r'\bmoon\b',
            r'\bto\s+the\s+moon\b',
            r'📈', r'🚀', r'⬆️', r'💚', r'🟢'
        ]
        
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in bullish_patterns)
    
    def has_bearish_indicators(self, text: str) -> bool:
        """Check if text contains bearish indicators."""
        bearish_patterns = [
            r'\bbear(?:ish)?\b',
            r'\bdown(?:ward)?\b',
            r'\bfall\b',
            r'\bdump\b',
            r'\bcrash\b',
            r'\bdrop\b',
            r'📉', r'💥', r'⬇️', r'❤️', r'🔴'
        ]
        
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in bearish_patterns)
    
    def extract_time_references(self, text: str) -> List[str]:
        """Extract time references from text."""
        time_patterns = [
            r'\b(?:in\s+)?(\d+)\s*(?:minutes?|mins?|m)\b',
            r'\b(?:in\s+)?(\d+)\s*(?:hours?|hrs?|h)\b',
            r'\b(?:in\s+)?(\d+)\s*(?:days?|d)\b',
            r'\b(?:in\s+)?(\d+)\s*(?:weeks?|w)\b',
            r'\b(today|tomorrow|tonight)\b',
            r'\b(short\s+term|long\s+term)\b',
        ]
        
        time_refs = []
        for pattern in time_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            time_refs.extend(matches)
        
        return time_refs
    
    def clean_symbol(self, symbol: str) -> str:
        """Clean and normalize trading symbol."""
        if not symbol:
            return ""
        
        # Remove common prefixes/suffixes
        symbol = symbol.upper().strip()
        symbol = re.sub(r'^(CRYPTO:|COIN:|TOKEN:)', '', symbol)
        symbol = re.sub(r'(USD|USDC|PERP|FUTURES?)$', '', symbol)
        
        # Remove special characters
        symbol = re.sub(r'[^A-Z0-9]', '', symbol)
        
        return symbol
    
    def is_valid_symbol(self, symbol: str) -> bool:
        """Check if symbol is valid trading symbol format."""
        if not symbol:
            return False
        
        # Must be 2-10 characters, alphanumeric
        if not re.match(r'^[A-Z0-9]{2,10}$', symbol.upper()):
            return False
        
        # Should not be all numbers
        if symbol.isdigit():
            return False
        
        return True 