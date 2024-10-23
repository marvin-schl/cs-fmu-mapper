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

    def generate_schedule(self, **kwargs) -> pd.DataFrame:
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
        times = kwargs.setdefault("times", None)
        duration = kwargs.setdefault("duration", 4 * 86400)
        items = kwargs.setdefault("items", self.default_items)
        patterns = kwargs.setdefault("patterns", self.default_patterns)

        if times and not all([len(times) == len(patterns[item]) for item in items]):
            raise ValueError("Length of `times` and `patterns` must be the same.")

        t = np.arange(0, duration + 1, 3600)  # Hourly data points
        df = pd.DataFrame({"t": t})

        for i, item in enumerate(items, 1):
            pattern = self._get_pattern(item, str(i), patterns, kwargs)
            values = self._generate_values(times, pattern, duration, len(t))
            df[f"{self.column_prefix}{item}"] = values

        return df, kwargs

    @staticmethod
    def _get_pattern(
        item: str, index: str, patterns: Dict[str, List[int]], kwargs: Dict[str, Any]
    ) -> List[int]:
        return kwargs.get(
            item, kwargs.get(index, patterns.get(index, patterns.get(item, [])))
        )

    @staticmethod
    def _generate_values(
        times: List[int], pattern: List[int], duration: int, time_points: int
    ) -> np.ndarray:
        if times:
            daily_pattern = np.full(24, np.nan)

            for time, value in zip(times, pattern):
                daily_pattern[time] = value

            for i in range(len(daily_pattern)):
                if np.isnan(daily_pattern[i]):
                    if i == 0:
                        daily_pattern[i] = daily_pattern[times[-1]]
                    else:
                        daily_pattern[i] = daily_pattern[i - 1]
        else:
            seconds_per_segment = 86400 // len(pattern)
            daily_pattern = np.repeat(pattern, seconds_per_segment // 3600)

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
