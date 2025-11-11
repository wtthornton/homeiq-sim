from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import math


@dataclass
class Daylight:
  latitude: float

  def sunrise_sunset(self, d: date) -> tuple[datetime, datetime]:
    # Simple approximate model: day length varies sinusoidally with latitude effect.
    # Not astronomy-grade; good enough for cadence shaping.
    day_of_year = d.timetuple().tm_yday

    # Approx daylight hours (naive): 12 +/- 4 * sin seasonal, scaled by latitude
    lat_factor = min(max(abs(self.latitude)/60.0, 0.2), 1.2)
    daylight_hours = 12 + 4*math.sin(2*math.pi*(day_of_year-80)/365.0)*lat_factor
    daylight_hours = max(7.0, min(17.0, daylight_hours))

    mid = datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)
    sunrise = mid - timedelta(hours=daylight_hours/2)
    sunset  = mid + timedelta(hours=daylight_hours/2)
    return sunrise, sunset
