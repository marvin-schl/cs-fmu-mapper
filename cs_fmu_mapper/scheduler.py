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
        times = kwargs.get("times", [])
        duration = kwargs.get("duration", 2 * 86400)  # 48 hours in seconds
        items = kwargs.get("items", self.default_items)
        patterns = kwargs.get("patterns", self.default_patterns)

        t = np.arange(0, duration + 1, 3600)  # Hourly data points
        df = pd.DataFrame({"t": t})

        for i, item in enumerate(items, 1):
            pattern = self._get_pattern(item, str(i), patterns, kwargs)
            values = self._generate_values(times, pattern, duration, len(t))
            df[f"{self.column_prefix}{item}"] = values

        return df

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
