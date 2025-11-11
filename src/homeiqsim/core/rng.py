from dataclasses import dataclass

import numpy as np, random


@dataclass
class RNG:
  seed: int

  def __post_init__(self):
    random.seed(self.seed)
    self.np = np.random.default_rng(self.seed)

  def choice(self, items, p=None):
    return self.np.choice(items, p=p)

  def uniform(self, low, high, size=None):
    return self.np.uniform(low, high, size)

  def lognormal_by_median_p90(self, median: float, p90: float):
    # Solve for mu, sigma of lognormal given median and p90.
    # median = exp(mu); p90 = exp(mu + z90*sigma), z901.28155
    import math

    z90 = 1.2815515655446004
    mu = math.log(median)
    sigma = (math.log(p90) - mu)/z90
    return float(self.np.lognormal(mu, sigma))
