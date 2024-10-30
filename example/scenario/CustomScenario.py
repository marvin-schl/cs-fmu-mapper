from cs_fmu_mapper.components.scenario import ScenarioBase
from cs_fmu_mapper.scheduler import Scheduler

DEFAULT_PATTERNS = {
    "1": [19, 21, 22, 21, 18],
}

DEFAULT_ITEMS = ["u"]


class CustomScenario(ScenarioBase):
    def __init__(self):
        self.scheduler = Scheduler(
            DEFAULT_PATTERNS, DEFAULT_ITEMS, column_prefix="scen.out."
        )

    def generate_schedule(self, **kwargs):
        return self.scheduler.generate_schedule(**kwargs)


if __name__ == "__main__":
    print(
        CustomScenario().generate_schedule(
            duration=180000,
            items=["item1", "item2", "item3", "item4", "item0"],
            times=[7, 20],
            patterns={
                "1": [293.15, 293.15],
                "2": [293.15, 293.15],
                "3": [293.15, 293.15],
                "4": [293.15, 293.15],
                "5": [293.15, 293.15],
            },
        )
    )
