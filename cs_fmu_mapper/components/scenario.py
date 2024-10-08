import os

import pandas as pd
from cs_fmu_mapper.components.simulation_component import SimulationComponent
from cs_fmu_mapper.utils import chooseFile
from tqdm import tqdm


class Scenario(SimulationComponent):

    type = "scenario"

    def __init__(self, config, name):
        super(Scenario, self).__init__(config, name)
        self._scenarios = []
        self._load_scenarios(config["path"])
        self._is_finished = False
        self._progress = 0
        self._final_time = self._calculate_final_time()
        self._log.info(f"Final time of Scenario is: {self._final_time}s")

    def _load_scenarios(self, paths):
        if isinstance(paths, str):
            paths = [paths]

        for path in paths:
            self._log.info(f"Loading scenario from: {path}")
            if os.path.exists(path):
                if os.path.isfile(path):
                    scenario = pd.read_csv(path)
                elif os.path.isdir(path):
                    file = chooseFile(
                        path,
                        "Scenario path is a directory. Please choose a Scenario file:",
                    )
                    scenario = pd.read_csv(os.path.join(path, file), delimiter=",")
            else:
                raise FileNotFoundError(f"Scenario file not found at: {path}")

            assert (
                "t" in scenario.columns
            ),  f"Scenario file must contain a column 't'. Columns found: {str(self._scenario.columns)}. Make sure to use comma as delimiter."
            self._scenarios.append(scenario)

    def _calculate_final_time(self):
        return max(
            int(scenario.sort_values(by="t", ascending=False).iloc[0]["t"])
            for scenario in self._scenarios
        )

    def set_input_values(self, new_val):
        raise NotImplementedError("Scenario does not provide input values.")

    async def do_step(self, t, dt):
        if self._is_finished:
            return

        try:
            self._progress = t / self._final_time
            output_values = {}

            for scenario in self._scenarios:
                cur_val = (
                    scenario[scenario["t"] >= t]
                    .sort_values(by="t", ascending=True)
                    .iloc[0]
                )
                scenario_values = cur_val.to_dict()
                del scenario_values["t"]
                output_values.update(scenario_values)

            self.set_output_values(
                {
                    x: output_values[x]
                    for x in self.get_output_values().keys()
                    if x in output_values
                }
            )
        except Exception as e:
            self._log.debug(e)
            self._is_finished = True
            self._log.info(f"Scenario finished at t={t}")

    async def finalize(self):
        return True

    def is_finished(self):
        return self._is_finished

    def get_progress(self):
        return self._progress
