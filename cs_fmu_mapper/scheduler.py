from typing import Any, Dict, List

import numpy as np
import pandas as pd


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
        - `times` (List[int]): The times (hours) at which the pattern should be set. If not provided, the pattern will be repeated evenly over 24 hours and repeated over the duration.
        - `duration` (int): The duration of the schedule in seconds.
        - `items` (List[str]): The items to generate a schedule for.
        - `patterns` (Dict[str, List[int]]): The patterns to use for each item. If `times` is provided, the elements of this parameter must be of same length as `times`.

        ### Returns:
        - `pd.DataFrame`: A DataFrame containing the schedule.

        ### Examples:
        - `generate_schedule(times=[0, 8, 16], duration=26 * 3600, items=["item1", "item2"], patterns={"item1": [1, 0, 1], "item2": [0, 1, 0]})`
        This will generate a schedule for `item1` and `item2` with the pattern `[1, 0, 1]` and `[0, 1, 0]` respectively, set at 0:00, 8:00 and 16:00.

        - `generate_schedule(duration=48 * 3600, items=["item1", "item2"], patterns={"item1": [1, 0, 1], "item2": [0, 1, 0]})`
        This will generate a schedule for `item1` and `item2` with the pattern `[1, 0, 1]` and `[0, 1, 0]` respectively, streched evenly over 24 hours and repeated over 2 days (48 hours).
        """
        duration = kwargs.setdefault("duration", 4 * 86400)
        items = kwargs.setdefault("items", self.default_items)
        patterns = kwargs.setdefault("patterns", self.default_patterns)

        assert all(
            len(pattern) == len(next(iter(patterns.values())))
            for pattern in patterns.values()
        ), "All patterns must have the same length."

        times = kwargs.setdefault(
            "times",
            [
                int(i * (24 / len(next(iter(patterns.values())))))
                for i in range(len(next(iter(patterns.values()))))
            ],
        )

        assert len(times) == len(
            next(iter(patterns.values()))
        ), "Length of `times` and `patterns` must be the same."

        t = np.arange(0, duration + 1, 3600)  # Hourly data points
        df = pd.DataFrame({"t": t})

        kwargs["patterns"] = {}
        for i, item in enumerate(items, 1):
            pattern = self._get_pattern(item, str(i), patterns)
            kwargs["patterns"][item] = pattern
            values = self._generate_values(pattern, duration, len(t), times)
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
    ) -> np.ndarray:
        daily_pattern = np.full(24, np.nan)

        for time, value in zip(times, pattern):
            daily_pattern[time] = value

        for i in range(len(daily_pattern)):
            if np.isnan(daily_pattern[i]):
                if i == 0:
                    daily_pattern[i] = daily_pattern[times[-1]]
                else:
                    daily_pattern[i] = daily_pattern[i - 1]

        return np.tile(daily_pattern, duration // 86400 + 1)[:time_points]


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
        duration=26 * 3600,  # 26 hours
        items=["custom_item1", "custom_item2"],
        patterns={"custom_item1": [1, 0, 1], "custom_item2": [0, 1, 0]},
        times=[0, 8, 16],  # Set values at 0:00, 8:00, and 16:00
    )
    print("\nCustom Schedule:")
    print(custom_schedule)
