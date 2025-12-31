from dataclasses import dataclass
from enum import Enum
from typing import List, Dict
import os


@dataclass(frozen=True)
class AIConstants:
    # Model configuration
    MODEL_NAME: str = 'gemini-2.5-flash'

    # API Rate Limits (Free Tier with 20% buffer)
    MAX_REQUESTS_PER_MINUTE: int = 12  # 15 actual, use 12 for safety
    MAX_TOKENS_PER_MINUTE: int = 800000  # 1M actual, use 800k for safety
    MAX_REQUESTS_PER_DAY: int = 1200  # 1500 actual, use 1200 for safety

    # Token limits per request
    MAX_INPUT_TOKENS: int = 128000  # Gemini 1.5 Flash context window
    MAX_OUTPUT_TOKENS: int = 8192  # Max tokens in response

    # Generation parameters
    TEMPERATURE: float = 0.7  # 0 = deterministic, 1 = creative
    # 0.7 = good balance for educational content
    TOP_P: float = 0.9  # Nucleus sampling (keep top 90% probability mass)
    TOP_K: int = 40  # Consider top 40 tokens at each step

    # Retry configuration
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 1000  # 1 second (in milliseconds)
    BACKOFF_MULTIPLIER: int = 2

AI = AIConstants()