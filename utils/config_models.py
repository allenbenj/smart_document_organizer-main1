from pydantic import BaseModel


class MLOptimizerConfig(BaseModel):
    min_samples: int = 50
    similarity_threshold: float = 0.7
    max_optimization_age_hours: int = 24
