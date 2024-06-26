import pandas as pd
from tqdm import tqdm
import os
from utils import chooseFile
import logging
from components.simulation_component import SimulationComponent


class Scenario(SimulationComponent):

    type = "scenario"

    def __init__(self, config, name):
        super(Scenario, self).__init__(config, name)
        self._log.info("Using Scneario path: " + config["path"])
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
        self._finished = False
        self._final_time = self._scenario.sort_values(by="t", ascending=False).iloc[0][
            "t"
        ]
        self._pbar = tqdm(
            total=self._final_time,
            unit="s",
            bar_format="{l_bar}{bar}| {n_fmt}{unit}/{total_fmt}{unit} [{elapsed}<{remaining}]",
        )
        self._pbar_update_counter = 0

    def set_input_values(self, new_val):
        raise NotImplementedError("Scenario does not provide input values.")

    def _get_name_by_node(self, nodeID):
        for name in self._config["outputVar"].keys():
            if self._config["outputVar"][name]["nodeID"] == nodeID:
                return name

    def do_step(self, t, dt):
        self._pbar_update_counter = self._pbar_update_counter + 1
        if self._pbar_update_counter == int(1 / dt):
            self._pbar.update(1)
            self._pbar_update_counter = 0
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
            print(e)
            self._finished = True
            self._pbar.close()
            self._log.info("Scenario finished at .")

    def finalize(self):
        return True

    def is_finished(self):
        return self._finished
