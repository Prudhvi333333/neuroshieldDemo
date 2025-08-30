#!/usr/bin/env python3
"""
Minimal Base Agent - Week 6 Implementation
Lightweight base class for rule-based agents that don't require LLM functionality
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class MinimalBaseAgent(ABC):
    """Minimal base agent for rule-based security agents"""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def run(self, *args, **kwargs):
        """Abstract method that must be implemented by subclasses"""
        pass
    
    @abstractmethod
    async def execute(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Abstract async execute method for enhanced agents"""
        pass
