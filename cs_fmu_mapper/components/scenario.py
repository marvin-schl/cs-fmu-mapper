import os

import pandas as pd
from cs_fmu_mapper.components.simulation_component import SimulationComponent
from cs_fmu_mapper.utils import chooseFile
from tqdm import tqdm


class Scenario(SimulationComponent):

    type = "scenario"

    def __init__(self, config, name):
        super(Scenario, self).__init__(config, name)
        self._log.info("Using Scenario path: " + config["path"])
        if os.path.exists(config["path"]):
            if os.path.isfile(config["path"]):
                self._scenario = pd.read_csv(config["path"], delimiter=";")
            elif os.path.isdir(config["path"]):
                file = chooseFile(
                    config["path"],
                    "Scenario path is a directory. Please choose a Scenraio file:",
                )
                self._scenario = pd.read_csv(config["path"] + "/" + file, delimiter=";")
        else:
            raise FileNotFoundError("Scenario file not found at: " + config["path"])
        self._is_finished = False
        self._final_time = int(
            self._scenario.sort_values(by="t", ascending=False).iloc[0]["t"]
        )
        # Progress bar
        self._pbar = None
        self._pbar_update_counter = 0

    def create_progress_bar(self):
        self._pbar = tqdm(
            total=self._final_time,
            unit="s",
            bar_format="{l_bar}{bar}| {n_fmt}{unit}/{total_fmt}{unit} [{elapsed}<{remaining}]",
            dynamic_ncols=True,
            colour="green",
        )

    def update_progress_bar(self, dt):
        if dt >= 1:
            self._pbar.update(dt)
        else:
            self._pbar_update_counter += 1
            if self._pbar_update_counter == int(1 / dt):
                self._pbar.update(1)
                self._pbar_update_counter = 0

    def set_input_values(self, new_val):
        raise NotImplementedError("Scenario does not provide input values.")

    def _get_name_by_node(self, nodeID):
        for name in self._config["outputVar"].keys():
            if self._config["outputVar"][name]["nodeID"] == nodeID:
                return name

    async def do_step(self, t, dt):
        if self._is_finished:
            return
        if self._pbar is None:
            self.create_progress_bar()
        self.update_progress_bar(dt)
        try:
            cur_val = (
                self._scenario[self._scenario["t"] >= t]
                .sort_values(by="t", ascending=True)
                .iloc[0]
            )
            output_values = cur_val.to_dict()
            del output_values["t"]
            self.set_output_values(
                dict(
                    map(
                        lambda x: (x, output_values[self.get_node_by_name(x)]),
                        self.get_output_values().keys(),
                    )
                )
            )

        except Exception as e:
            self._log.debug(e)
            self._is_finished = True
            self._pbar.close()
            self._log.info("Scenario finished at t=" + str(t))

    async def finalize(self):
        return True

    def is_finished(self):
        return self._is_finished
