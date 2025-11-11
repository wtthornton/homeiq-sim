import random


def inject_faults(events, rng, rate_drop=0.005, rate_dup=0.003, rate_ooo=0.001):
  out = []
  for e in events:
    r = random.random()
    if r < rate_drop:
      continue
    out.append(e)
    if r < rate_drop + rate_dup:
      out.append(dict(e))  # duplicate
    if random.random() < rate_ooo and len(out) > 10:
      i = random.randint(0, len(out) - 6)
      out[i:i+5] = reversed(out[i:i+5])
  return out
