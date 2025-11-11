def synth_labels(home_ctx, drivers, rng):
  """
  Produce simple occupancy and hvac labels per month for training/eval.
  """
  return {
    "home_id": home_ctx["home_id"],
    "year": home_ctx["year"],
    "has_kids": bool(home_ctx.get("has_kids", False)),
    "wfh_ratio": float(home_ctx.get("wfh_ratio", 0.3)),
  }
