import importlib.util
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

import pandas as pd
import yaml
from cs_fmu_mapper.components.simulation_component import SimulationComponent
from cs_fmu_mapper.utils import chooseFile


class ScenarioBase(ABC):
    @abstractmethod
    def generate_schedule(self, **kwargs) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        pass


class Scenario(SimulationComponent):
    type = "scenario"

    def __init__(self, config, name):
        super(Scenario, self).__init__(config, name)
        self._scenario, self._scenario_params = self._load_scenarios(
            config["path"], config.get("parameters", {})
        )

        self._is_finished = False
        self._progress = 0
        self._final_time = self._calculate_final_time()
        self._output_path = config.get("outputFolder", None)
        self._log.info(f"Final time of Scenario is: {self._final_time}s")

        if self._output_path:
            self._export_scenario_data()

    def _load_scenarios(self, paths, params):
        scenarios = []
        all_scenario_params = {}
        if isinstance(paths, str):
            paths = [paths]

        for path in paths:
            self._log.info(f"Loading scenario from: {path}")
            if path.endswith(".py"):
                scenario, scenario_params = self._load_python_scenario(
                    path, params.get(path, {})
                )
            else:
                scenario = self._load_csv_scenario(path)

            assert (
                "t" in scenario.columns
            ), f"Scenario {path} must contain a column 't'."
            scenarios.append(scenario)
            all_scenario_params[path] = scenario_params

        # merge all scenarios into one dataframe
        merged_scenario = pd.DataFrame()
        for scenario in scenarios:
            if merged_scenario.empty:
                merged_scenario = scenario
            else:
                # Merge on 't' column and fill forward missing values
                merged_scenario = pd.merge_asof(
                    merged_scenario, scenario, on="t", direction="forward"
                )

        # Fill any remaining NaN values with forward fill
        merged_scenario = merged_scenario.ffill()

        return merged_scenario, all_scenario_params

    def _load_python_scenario(self, path, params):
        spec = importlib.util.spec_from_file_location("scenario_module", path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Failed to load scenario from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        scenario_classes = [
            cls
            for cls in module.__dict__.values()
            if isinstance(cls, type)
            and issubclass(cls, ScenarioBase)
            and cls != ScenarioBase
        ]
        if not scenario_classes:
            raise ValueError(f"No ScenarioBase subclass found in {path}")

        scenario_class = scenario_classes[0]
        scenario_instance = scenario_class()
        return scenario_instance.generate_schedule(**params)

    def _load_csv_scenario(self, path):
        if os.path.exists(path):
            if os.path.isfile(path):
                return pd.read_csv(path)
            elif os.path.isdir(path):
                file = chooseFile(
                    path,
                    "Scenario path is a directory. Please choose a Scenario file:",
                )
                return pd.read_csv(os.path.join(path, file))
        else:
            raise FileNotFoundError(f"Scenario file not found at: {path}")

    def _calculate_final_time(self):
        return int(self._scenario.sort_values(by="t", ascending=False).iloc[0]["t"])

    def set_input_values(self, new_val):
        raise NotImplementedError("Scenario does not provide input values.")

    async def do_step(self, t, dt):
        if self._is_finished:
            return

        try:
            self._progress = t / self._final_time
            output_values = {}

            cur_val = (
                self._scenario[self._scenario["t"] >= t]
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

    def _export_scenario_data(self):
        os.makedirs(self._output_path, exist_ok=True)

        for filename, data, export_func in [
            ("scenario.csv", self._scenario, lambda f, d: d.to_csv(f, index=False)),
            (
                "scenario_parameters.yaml",
                self._scenario_params,
                lambda f, d: yaml.dump(d, f, default_flow_style=False),
            ),
        ]:
            output_file = os.path.join(self._output_path, filename)
            with open(output_file, "w") as f:
                export_func(f, data)
            self._log.info(f"Exported {filename.split('.')[0]} to: {output_file}")
