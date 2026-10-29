"""
Model Configuration for Exercise Generation

Central configuration to easily switch between LLM models based on 
content type, cost constraints, or quality requirements.
"""

from dataclasses import dataclass
from typing import Literal

ModelName = Literal[
    "gpt-4o-mini",
    "gpt-4o", 
    "claude-3-haiku",
    "claude-3.5-sonnet"
]


@dataclass
class ModelConfig:
    """Configuration for a specific LLM model"""
    provider: Literal["openai", "anthropic"]
    model_id: str
    max_tokens: int = 2000
    temperature: float = 0.7
    use_json_mode: bool = True


# Model definitions
MODELS = {
    "gpt-4o-mini": ModelConfig(
        provider="openai",
        model_id="gpt-4o-mini",
        max_tokens=2000,
        temperature=0.7,
        use_json_mode=True
    ),
    "gpt-4o": ModelConfig(
        provider="openai",
        model_id="gpt-4o",
        max_tokens=2000,
        temperature=0.7,
        use_json_mode=True
    ),
    "claude-3-haiku": ModelConfig(
        provider="anthropic",
        model_id="claude-3-haiku-20240307",
        max_tokens=2000,
        temperature=0.7,
        use_json_mode=False  # Claude uses prompt-based JSON
    ),
    "claude-3.5-sonnet": ModelConfig(
        provider="anthropic",
        model_id="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        temperature=0.7,
        use_json_mode=False
    ),
}


# ============================================================================
# STRATEGY CONFIGURATIONS
# ============================================================================

# Strategy 1: Premium Quality (Best for paid products)
PREMIUM_STRATEGY = {
    "default": "gpt-4o",
    "estimated_cost_per_video": 0.007,
    "description": "Use GPT-4o for everything - highest quality"
}

# Strategy 2: Tiered Approach (Balanced cost/quality)
TIERED_STRATEGY = {
    "high_value": "gpt-4o",  # Complex topics
    "standard": "claude-3-haiku",  # Basic topics
    "estimated_cost_per_video": 0.0053,  # Weighted average
    "description": "Use premium model for complex content, budget for basic"
}

# Strategy 3: Budget (MVP/Testing)
BUDGET_STRATEGY = {
    "default": "claude-3-haiku",
    "estimated_cost_per_video": 0.00082,
    "description": "Use Claude Haiku for everything - lowest cost"
}

# ============================================================================
# ACTIVE STRATEGY - CHANGE THIS TO SWITCH STRATEGIES
# ============================================================================

ACTIVE_STRATEGY = PREMIUM_STRATEGY  # ← Change this line to switch strategies


# ============================================================================
# CONTENT CLASSIFICATION
# ============================================================================

HIGH_VALUE_TOPICS = [
    "algebra",
    "geometry", 
    "trigonometry",
    "calculus",
    "statistics",
    "probability",
    "exam prep",
    "sat math",
    "act math",
]

HIGH_VALUE_KEYWORDS = [
    "exam",
    "test prep",
    "advanced",
    "challenge",
    "competition",
]


def select_model_for_content(
    video_metadata: dict,
    strategy: dict = ACTIVE_STRATEGY
) -> ModelName:
    """
    Select appropriate model based on content and strategy.
    
    Args:
        video_metadata: Dict with 'title', 'topic', 'grade_level', etc.
        strategy: One of the strategy configs above
    
    Returns:
        Model name to use for this content
    """
    
    # Single-model strategies
    if "default" in strategy and "high_value" not in strategy:
        return strategy["default"]
    
    # Tiered strategy - determine if content is high value
    if "high_value" in strategy:
        topic = video_metadata.get('topic', '').lower()
        title = video_metadata.get('title', '').lower()
        grade_level = video_metadata.get('grade_level', 0)
        
        # Check if high-value topic
        if any(hvt in topic for hvt in HIGH_VALUE_TOPICS):
            return strategy["high_value"]
        
        # Check if high-value keywords in title
        if any(kw in title for kw in HIGH_VALUE_KEYWORDS):
            return strategy["high_value"]
        
        # Check grade level (8+ is typically more advanced)
        if grade_level >= 8:
            return strategy["high_value"]
        
        # Default to standard model
        return strategy["standard"]
    
    # Fallback
    return "gpt-4o"


def get_model_config(model_name: ModelName) -> ModelConfig:
    """Get configuration for a specific model"""
    return MODELS[model_name]


def estimate_total_cost(
    num_videos: int,
    strategy: dict = ACTIVE_STRATEGY
) -> float:
    """
    Estimate total cost for generating exercises.
    
    Args:
        num_videos: Number of videos to process
        strategy: Strategy configuration
    
    Returns:
        Estimated cost in USD
    """
    return num_videos * strategy["estimated_cost_per_video"]


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Example 1: Get model for specific content
    video1 = {
        "title": "Introduction to Algebra - Solving Linear Equations",
        "topic": "algebra",
        "grade_level": 8
    }
    
    model1 = select_model_for_content(video1)
    print(f"Video: {video1['title']}")
    print(f"Selected Model: {model1}")
    print(f"Strategy: {ACTIVE_STRATEGY['description']}\n")
    
    # Example 2: Basic arithmetic video
    video2 = {
        "title": "Adding Two-Digit Numbers",
        "topic": "basic arithmetic",
        "grade_level": 2
    }
    
    model2 = select_model_for_content(video2)
    print(f"Video: {video2['title']}")
    print(f"Selected Model: {model2}\n")
    
    # Example 3: Cost estimation
    print("="*60)
    print("COST ESTIMATIONS")
    print("="*60)
    
    for num_videos in [1635, 4904]:
        cost_premium = estimate_total_cost(num_videos, PREMIUM_STRATEGY)
        cost_tiered = estimate_total_cost(num_videos, TIERED_STRATEGY)
        cost_budget = estimate_total_cost(num_videos, BUDGET_STRATEGY)
        
        print(f"\nFor {num_videos:,} videos:")
        print(f"  Premium Strategy: ${cost_premium:.2f}")
        print(f"  Tiered Strategy:  ${cost_tiered:.2f}")
        print(f"  Budget Strategy:  ${cost_budget:.2f}")
    
    print("\n" + "="*60)
    print(f"ACTIVE STRATEGY: {ACTIVE_STRATEGY['description']}")
    print("="*60)
