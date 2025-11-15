"""Event loop system for continuous simulation.

Manages scheduled tasks, event dispatch, and coordination of behavior engines.
"""
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple
import asyncio
import heapq
from threading import Thread, Event
import logging

from .clock import SimulationClock
from .state import StateManager

logger = logging.getLogger(__name__)


class ScheduledTask:
    """Represents a scheduled task in the event loop."""

    def __init__(
        self,
        run_at: datetime,
        callback: Callable,
        args: tuple = (),
        kwargs: dict = None,
        repeat: Optional[timedelta] = None,
        task_id: Optional[str] = None,
    ):
        """Initialize scheduled task.

        Args:
            run_at: When to run the task
            callback: Function to call
            args: Positional arguments for callback
            kwargs: Keyword arguments for callback
            repeat: If set, task repeats with this interval
            task_id: Optional unique identifier
        """
        self.run_at = run_at
        self.callback = callback
        self.args = args
        self.kwargs = kwargs or {}
        self.repeat = repeat
        self.task_id = task_id

    def __lt__(self, other):
        """Compare for heap sorting."""
        return self.run_at < other.run_at


class EventLoop:
    """Main event loop for the Home Assistant simulator."""

    def __init__(
        self,
        clock: SimulationClock,
        state_manager: StateManager,
    ):
        """Initialize event loop.

        Args:
            clock: Simulation clock
            state_manager: State manager instance
        """
        self.clock = clock
        self.state_manager = state_manager
        self._tasks: List[ScheduledTask] = []
        self._running = False
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._task_counter = 0

    def schedule_task(
        self,
        delay: timedelta,
        callback: Callable,
        args: tuple = (),
        kwargs: dict = None,
        repeat: Optional[timedelta] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Schedule a task to run after a delay.

        Args:
            delay: Time to wait before running
            callback: Function to call
            args: Positional arguments
            kwargs: Keyword arguments
            repeat: If set, repeat with this interval
            task_id: Optional task identifier

        Returns:
            Task ID
        """
        run_at = self.clock.now() + delay
        if task_id is None:
            self._task_counter += 1
            task_id = f"task_{self._task_counter}"

        task = ScheduledTask(run_at, callback, args, kwargs, repeat, task_id)
        heapq.heappush(self._tasks, task)
        return task_id

    def schedule_at(
        self,
        run_at: datetime,
        callback: Callable,
        args: tuple = (),
        kwargs: dict = None,
        repeat: Optional[timedelta] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Schedule a task to run at a specific time.

        Args:
            run_at: When to run the task
            callback: Function to call
            args: Positional arguments
            kwargs: Keyword arguments
            repeat: If set, repeat with this interval
            task_id: Optional task identifier

        Returns:
            Task ID
        """
        if task_id is None:
            self._task_counter += 1
            task_id = f"task_{self._task_counter}"

        task = ScheduledTask(run_at, callback, args, kwargs, repeat, task_id)
        heapq.heappush(self._tasks, task)
        return task_id

    def schedule_interval(
        self,
        interval: timedelta,
        callback: Callable,
        args: tuple = (),
        kwargs: dict = None,
        task_id: Optional[str] = None,
        run_immediately: bool = False,
    ) -> str:
        """Schedule a task to run at regular intervals.

        Args:
            interval: Time between executions
            callback: Function to call
            args: Positional arguments
            kwargs: Keyword arguments
            task_id: Optional task identifier
            run_immediately: If True, run immediately then repeat

        Returns:
            Task ID
        """
        delay = timedelta(0) if run_immediately else interval
        return self.schedule_task(delay, callback, args, kwargs, repeat=interval, task_id=task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task.

        Args:
            task_id: The task ID to cancel

        Returns:
            True if cancelled, False if not found
        """
        # Mark for removal (actual removal happens in run loop)
        for task in self._tasks:
            if task.task_id == task_id:
                task.task_id = None  # Mark as cancelled
                return True
        return False

    def start(self) -> None:
        """Start the event loop in a background thread."""
        if self._running:
            logger.warning("Event loop already running")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Event loop started")

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the event loop.

        Args:
            timeout: Maximum time to wait for clean shutdown
        """
        if not self._running:
            return

        logger.info("Stopping event loop")
        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

        logger.info("Event loop stopped")

    def _run_loop(self) -> None:
        """Main event loop (runs in background thread)."""
        while self._running and not self._stop_event.is_set():
            try:
                # Process due tasks
                now = self.clock.now()

                while self._tasks and self._tasks[0].run_at <= now:
                    task = heapq.heappop(self._tasks)

                    # Skip cancelled tasks
                    if task.task_id is None:
                        continue

                    try:
                        # Execute task
                        task.callback(*task.args, **task.kwargs)

                        # Reschedule if repeating
                        if task.repeat:
                            task.run_at = now + task.repeat
                            heapq.heappush(self._tasks, task)

                    except Exception as e:
                        logger.error(f"Error executing task {task.task_id}: {e}")

                # Sleep until next task or a reasonable interval
                if self._tasks:
                    next_task_time = self._tasks[0].run_at
                    wall_sleep = self.clock.wall_time_until(next_task_time)
                    if wall_sleep and wall_sleep > 0:
                        # Sleep for min of calculated time or 1 second
                        self._stop_event.wait(min(wall_sleep, 1.0))
                else:
                    # No tasks, sleep briefly
                    self._stop_event.wait(0.1)

            except Exception as e:
                logger.error(f"Error in event loop: {e}")
                self._stop_event.wait(0.1)

    def get_pending_tasks(self) -> int:
        """Get count of pending tasks."""
        return len([t for t in self._tasks if t.task_id is not None])

    def is_running(self) -> bool:
        """Check if event loop is running."""
        return self._running
