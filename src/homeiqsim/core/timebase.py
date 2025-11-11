from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class Timebase:
  year: int

  def days(self):
    d = datetime(self.year, 1, 1, tzinfo=timezone.utc)
    while d.year == self.year:
      yield d.date()
      d += timedelta(days=1)
