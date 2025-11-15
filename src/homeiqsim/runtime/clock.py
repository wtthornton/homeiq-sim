"""Simulation clock for time acceleration and control.

Provides a virtual clock that can run faster or slower than real time,
allowing for time travel and fast-forward capabilities.
"""
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Optional
import time


class SimulationClock:
    """Virtual clock for simulation with time acceleration."""

    def __init__(
        self,
        start_time: Optional[datetime] = None,
        speed: float = 1.0,
        paused: bool = False,
    ):
        """Initialize simulation clock.

        Args:
            start_time: Initial simulation time (default: current UTC time)
            speed: Time acceleration factor (1.0 = real-time, 10.0 = 10x faster)
            paused: Whether to start paused
        """
        self._lock = RLock()
        self._start_time = start_time or datetime.now(timezone.utc)
        self._sim_time = self._start_time
        self._wall_start = time.time()
        self._speed = speed
        self._paused = paused
        self._pause_time: Optional[float] = None
        self._pause_sim_time: Optional[datetime] = None

    def now(self) -> datetime:
        """Get current simulation time.

        Returns:
            Current datetime in the simulation
        """
        with self._lock:
            if self._paused:
                return self._pause_sim_time or self._sim_time

            wall_elapsed = time.time() - self._wall_start
            sim_elapsed = timedelta(seconds=wall_elapsed * self._speed)
            return self._start_time + sim_elapsed

    def set_time(self, new_time: datetime) -> None:
        """Jump to a specific simulation time.

        Args:
            new_time: The time to jump to
        """
        with self._lock:
            self._start_time = new_time
            self._wall_start = time.time()
            if self._paused:
                self._pause_sim_time = new_time

    def set_speed(self, speed: float) -> None:
        """Change time acceleration factor.

        Args:
            speed: New speed multiplier (must be > 0)
        """
        if speed <= 0:
            raise ValueError("Speed must be positive")

        with self._lock:
            # Update start time to current to avoid jumps
            current = self.now()
            self._start_time = current
            self._wall_start = time.time()
            self._speed = speed

    def get_speed(self) -> float:
        """Get current time acceleration factor."""
        with self._lock:
            return self._speed

    def pause(self) -> None:
        """Pause the simulation clock."""
        with self._lock:
            if not self._paused:
                self._pause_time = time.time()
                self._pause_sim_time = self.now()
                self._paused = True

    def resume(self) -> None:
        """Resume the simulation clock."""
        with self._lock:
            if self._paused:
                # Reset wall start to now, maintaining sim time
                self._start_time = self._pause_sim_time or self._sim_time
                self._wall_start = time.time()
                self._paused = False
                self._pause_time = None
                self._pause_sim_time = None

    def is_paused(self) -> bool:
        """Check if clock is paused."""
        with self._lock:
            return self._paused

    def advance(self, delta: timedelta) -> None:
        """Advance simulation time by a fixed amount.

        Args:
            delta: Amount of time to advance
        """
        with self._lock:
            current = self.now()
            self.set_time(current + delta)

    def sleep(self, duration: float) -> None:
        """Sleep for a duration in simulation time.

        Args:
            duration: Seconds to sleep in simulation time
        """
        if self._paused:
            # Just sleep real-time if paused
            time.sleep(duration)
        else:
            # Calculate wall time needed
            wall_duration = duration / self._speed
            time.sleep(wall_duration)

    def time_until(self, target: datetime) -> Optional[float]:
        """Calculate simulation seconds until a target time.

        Args:
            target: Target datetime

        Returns:
            Seconds until target, or None if target is in the past
        """
        current = self.now()
        if target <= current:
            return None

        delta = (target - current).total_seconds()
        return delta

    def wall_time_until(self, target: datetime) -> Optional[float]:
        """Calculate wall clock seconds until a target simulation time.

        Args:
            target: Target datetime in simulation

        Returns:
            Real seconds until target, or None if target is in the past
        """
        sim_seconds = self.time_until(target)
        if sim_seconds is None:
            return None

        return sim_seconds / self._speed

    def __repr__(self) -> str:
        """String representation."""
        status = "paused" if self._paused else f"{self._speed}x"
        return f"SimulationClock({self.now().isoformat()}, {status})"
