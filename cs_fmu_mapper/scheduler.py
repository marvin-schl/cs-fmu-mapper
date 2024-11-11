from typing import Any, Dict, List, Literal

import numpy as np
import pandas as pd

TimeUnit = Literal["days", "hours", "minutes", "seconds"]


class Scheduler:
    """
    A class for generating schedules based on specified patterns, times and items.
    """

    def __init__(
        self,
        patterns: Dict[str, List[float]],
        items: List[str] | None = None,
        column_prefix: str = "scen.out.",
        duration: int = 4 * 86400,
        time_unit: TimeUnit = "hours",
        times: List[int] | None = None,
        start_time: int = 0,
    ):
        self.patterns = patterns
        self.items = items or list(patterns.keys())
        self.column_prefix = column_prefix
        self.duration = duration
        self.time_unit = time_unit
        self.times = times
        self.start_time = start_time
        self.validate_parameters()
        self._calculate_times()

    def _calculate_times(self):
        """
        Calculate the maximum value and step size based on the time unit.
        If times is not provided, calculate times (evenly spaced).
        """
        if self.time_unit == "days":
            self.max_value = 7
            self.step = 86400  # 1 day in seconds
        elif self.time_unit == "hours":
            self.max_value = 24
            self.step = 3600  # 1 hour in seconds
        elif self.time_unit == "minutes":
            self.max_value = 60
            self.step = 60  # 1 minute in seconds
        elif self.time_unit == "seconds":
            self.max_value = 60
            self.step = 1  # 1 second
        else:
            raise ValueError(f"time_unit must be one of {TimeUnit}")
        # if times is not provided, calculate times (evenly spaced)
        if self.times is None:
            self.times = [
                int(i * (self.max_value / len(next(iter(self.patterns.values())))))
                for i in range(len(next(iter(self.patterns.values()))))
            ]
        # Validate times based on time unit
        if not all(0 <= t < self.max_value for t in self.times):
            raise ValueError(
                f"All times must be between 0 and {self.max_value-1} for {self.time_unit} unit"
            )

        assert len(self.times) == len(
            next(iter(self.patterns.values()))
        ), "Length of `times` and `patterns` must be the same."

    def validate_parameters(self):
        """
        Assert that the parameters are valid.
        """
        # Validate patterns
        if not all(
            len(pattern) == len(next(iter(self.patterns.values())))
            for pattern in self.patterns.values()
        ):
            raise ValueError("All patterns must have the same length.")

        if self.duration <= 0:
            raise ValueError("Duration must be at least 1 second")
        if not isinstance(self.duration, int):
            raise ValueError("Duration must be an integer.")

        if self.times is not None and not isinstance(self.times, list):
            raise ValueError("Times must be a list.")

        if len(self.items) > len(self.patterns):
            raise ValueError(
                "Number of items must be less than or equal to number of patterns."
            )

        if self.start_time < 0:
            raise ValueError("start_time cannot be negative")

    def generate_scenario(self):
        """Generate a schedule based on the specified parameters."""
        # Create time points array with appropriate step
        t = np.arange(self.start_time, self.start_time + self.duration + 1, self.step)
        df = pd.DataFrame({"t": t})

        patterns = {}
        for i, item in enumerate(self.items, 1):
            pattern = self._get_pattern(item, str(i), self.patterns)
            patterns[item] = pattern
            values = self._generate_values(
                pattern, self.duration, len(t), self.times, self.step
            )
            df[f"{self.column_prefix}{item}"] = values
        self.patterns = patterns
        parameters = {
            "duration": self.duration,
            "items": self.items,
            "patterns": self.patterns,
            "times": self.times,
            "time_unit": self.time_unit,
            "column_prefix": self.column_prefix,
            "start_time": self.start_time,
        }
        return df, parameters

    @staticmethod
    def _get_pattern(
        item: str, index: str, patterns: Dict[str, List[float]]
    ) -> List[float]:
        return patterns.get(item, patterns.get(index, []))

    @staticmethod
    def _generate_values(
        pattern: List[float],
        duration: int,
        time_points: int,
        times: List[int],
        step: int,
    ) -> np.ndarray:
        # Calculate number of values needed for one cycle
        cycle_length = step * (60 if step < 3600 else 24)
        values_per_cycle = cycle_length // step

        # Create the pattern for one cycle
        cycle_pattern = np.full(values_per_cycle, np.nan)

        # Fill in the specified values
        for time, value in zip(times, pattern):
            cycle_pattern[time] = value

        # Forward fill NaN values
        for i in range(len(cycle_pattern)):
            if np.isnan(cycle_pattern[i]):
                if i == 0:
                    cycle_pattern[i] = cycle_pattern[times[-1]]
                else:
                    cycle_pattern[i] = cycle_pattern[i - 1]

        # Repeat the pattern for the entire duration
        num_repeats = (duration // cycle_length) + 1
        return np.tile(cycle_pattern, num_repeats)[:time_points]


if __name__ == "__main__":
    # Create a Scheduler instance
    scheduler = Scheduler(
        duration=7 * 86400,
        items=["custom_item1", "custom_item2"],
        patterns={"custom_item1": [2, 0, 1], "custom_item2": [3, 1, 0]},
        time_unit="days",
        column_prefix="test.",
        times=[0, 1, 2],
        start_time=86400,
    )
    # Generate scenario
    custom_schedule = scheduler.generate_scenario()
    print(custom_schedule[1])
    print(custom_schedule[0])
