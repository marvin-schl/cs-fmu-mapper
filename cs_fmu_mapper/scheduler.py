from typing import Any, Dict, List, Literal

import numpy as np
import pandas as pd

TimeUnit = Literal["hours", "minutes", "seconds"]


class Scheduler:
    """
    A class for generating schedules based on specified patterns, times and items.
    """

    def __init__(
        self,
        default_patterns: Dict[str, List[int]],
        default_items: List[str],
        column_prefix: str = "scen.out.",
    ):
        self.default_patterns = default_patterns
        self.default_items = default_items
        self.column_prefix = column_prefix

    def generate_schedule(self, **kwargs):
        """
        Generate a schedule based on the specified parameters.

        ### Parameters:
        - `times` (List[int]): The times at which the pattern should be set.
          Interpretation depends on time_unit parameter.
        - `time_unit` (str): The unit for the times parameter. Can be 'hours' (0-23),
          'minutes' (0-59), or 'seconds' (0-59). Defaults to 'hours'.
        - `duration` (int): The duration of the schedule in seconds.
        - `items` (List[str]): The items to generate a schedule for.
        - `patterns` (Dict[str, List[int]]): The patterns to use for each item.
          Must be of same length as `times`.

        ### Returns:
        - `pd.DataFrame`: A DataFrame containing the schedule.

        ### Examples:
        - `generate_schedule(times=[0, 8, 16], time_unit="hours", duration=26 * 3600, items=["item1", "item2"], patterns={"item1": [1, 0, 1], "item2": [0, 1, 0]})`
        This will generate a schedule for `item1` and `item2` with the pattern `[1, 0, 1]` and `[0, 1, 0]` respectively, set at 0:00, 8:00 and 16:00.

        - `generate_schedule(times=[0, 30, 59], time_unit="minutes", duration=3 * 3600, items=["item1", "item2"], patterns={"item1": [1, 0, 1], "item2": [0, 1, 0]})`
        This will generate a schedule for `item1` and `item2` with the pattern `[1, 0, 1]` and `[0, 1, 0]` respectively, set at 0:00, 0:30 and 0:59 and repeated over 3 hours.
        """
        duration = kwargs.setdefault("duration", 4 * 86400)
        items = kwargs.setdefault("items", self.default_items)
        patterns = kwargs.setdefault("patterns", self.default_patterns)
        time_unit = kwargs.setdefault("time_unit", "hours")

        assert time_unit in [
            "hours",
            "minutes",
            "seconds",
        ], "time_unit must be 'hours', 'minutes', or 'seconds'"

        assert all(
            len(pattern) == len(next(iter(patterns.values())))
            for pattern in patterns.values()
        ), "All patterns must have the same length."

        # Default times based on pattern length and time unit
        pattern_length = len(next(iter(patterns.values())))
        if time_unit == "hours":
            max_value = 24
            step = 3600  # 1 hour in seconds
        elif time_unit == "minutes":
            max_value = 60
            step = 60  # 1 minute in seconds
        else:  # seconds
            max_value = 60
            step = 1  # 1 second

        times = kwargs.setdefault(
            "times",
            [int(i * (max_value / pattern_length)) for i in range(pattern_length)],
        )

        # Validate times based on time unit
        assert all(
            0 <= t < max_value for t in times
        ), f"All times must be between 0 and {max_value-1} for {time_unit} unit"
        assert len(times) == len(
            next(iter(patterns.values()))
        ), "Length of `times` and `patterns` must be the same."

        # Create time points array with appropriate step
        t = np.arange(0, duration + 1, step)
        df = pd.DataFrame({"t": t})

        kwargs["patterns"] = {}
        for i, item in enumerate(items, 1):
            pattern = self._get_pattern(item, str(i), patterns)
            kwargs["patterns"][item] = pattern
            values = self._generate_values(pattern, duration, len(t), times, step)
            df[f"{self.column_prefix}{item}"] = values

        return df, kwargs

    @staticmethod
    def _get_pattern(
        item: str, index: str, patterns: Dict[str, List[int]]
    ) -> List[int]:
        return patterns.get(item, patterns.get(index, []))

    @staticmethod
    def _generate_values(
        pattern: List[int],
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
    # Define default patterns and items
    default_patterns = {"1": [0, 1, 0, 1], "2": [1, 0, 1, 0], "3": [0, 1, 1, 0]}
    default_items = ["item1", "item2", "item3"]

    # Create a Scheduler instance
    scheduler = Scheduler(default_patterns, default_items)

    # Generate a schedule with default settings
    default_schedule = scheduler.generate_schedule()
    print("Default Schedule:")
    print(default_schedule)

    # Generate a schedule with custom settings
    custom_schedule = scheduler.generate_schedule(
        duration=26 * 3600,  # 2 hours
        items=["custom_item1", "custom_item2"],
        patterns={"custom_item1": [1, 0, 1], "custom_item2": [0, 1, 0]},
        time_unit="hours",
        times=[0, 8, 16],  # Set values at 0:00, 8:00, and 16:00
    )
    print("\nCustom Schedule:")
    print(custom_schedule[0].head(24))
