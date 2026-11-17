"""Finite Bernoulli information model adapted from the user-supplied curiosity v0.1.
Operational probabilities, not truth of arbitrary claims. No tools or LLMs.
"""
from dataclasses import dataclass, field
import math
import statistics


def entropy(probabilities: list[float] | tuple[float, ...]) -> float:
    return -sum(p * math.log(p) for p in probabilities if p > 0)


@dataclass
class Belief:
    grid: list[float] = field(default_factory=lambda: [0.1, 0.3, 0.5, 0.7, 0.9])
    weights: list[float] = field(default_factory=lambda: [0.2] * 5)
    observations: int = 0
    progress: list[float] = field(default_factory=list)

    def __post_init__(self):
        if not self.grid or len(self.grid) != len(self.weights):
            raise ValueError('Invalid hypothesis dimensions')
        if any(not math.isfinite(p) or not 0 < p < 1 for p in self.grid):
            raise ValueError('Probabilities must be finite and inside (0,1)')
        if any(not math.isfinite(w) or w < 0 for w in self.weights):
            raise ValueError('Invalid posterior weights')
        if not math.isclose(sum(self.weights), 1, abs_tol=1e-9):
            raise ValueError('Posterior must sum to one')
        if type(self.observations) is not int or self.observations < 0:
            raise ValueError('Invalid observation count')
        if any(not math.isfinite(g) or not -1 <= g <= 1 for g in self.progress):
            raise ValueError('Invalid progress observations')

    @property
    def mean(self) -> float:
        return sum(w * p for w, p in zip(self.weights, self.grid))

    def posterior(self, outcome: int) -> list[float]:
        if type(outcome) is not int or outcome not in (0, 1):
            raise ValueError('Binary integer outcome required')
        unnormalized = [w * (p if outcome else 1-p)
                        for w, p in zip(self.weights, self.grid)]
        total = sum(unnormalized)
        return [w / total for w in unnormalized]

    @property
    def information_gain(self) -> float:
        p = self.mean
        expected = p * entropy(self.posterior(1)) + (1-p) * entropy(self.posterior(0))
        return max(0.0, entropy(self.weights) - expected)

    @property
    def surprise_baseline(self) -> float:
        # Predictive entropy remains high even after learning a fair coin.
        return entropy([self.mean, 1-self.mean])

    @property
    def conservative_progress(self) -> float:
        if len(self.progress) < 4:
            return 0.0
        sample = self.progress[-12:]
        # Heuristic uncertainty penalty, not a calibrated confidence bound.
        estimate = statistics.mean(sample) - statistics.stdev(sample) / math.sqrt(len(sample))
        return max(0.0, estimate)

    def observe(self, outcome: int, progress: float | None = None):
        if progress is not None and (not math.isfinite(progress) or not -1 <= progress <= 1):
            raise ValueError('Invalid progress')
        updated = self.posterior(outcome)
        self.weights = updated
        self.observations += 1
        if progress is not None:
            self.progress.append(progress)
            self.progress = self.progress[-12:]


