import logging
from abc import ABC, abstractmethod

from tqdm import tqdm


class SimulationComponent(ABC):

    @classmethod
    def get_subclasses(cls):
        for subclass in cls.__subclasses__():
            if not subclass.__module__.startswith("cs_fmu_mapper.components"):
                pass
            else:
                yield from subclass.get_subclasses()
                yield subclass

    def __init__(self, config, name):
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.info("Initializing " + str(self.__class__.__name__) + ".")
        self._config: dict = config
        self._name: str = name
        self._is_finished: bool = True

        self._input_values: dict[str, float] = {}
        self._output_values: dict[str, float] = {}

        if "inputVar" in self._config.keys():
            self._init_input_values()
        if "outputVar" in self._config.keys():
            self._init_output_values()

        self._pbar: tqdm = None
        self._pbar_update_counter: int = 0

    def _init_input_values(self):
        self._input_values = {
            k: self._config["inputVar"][k]["init"]
            for k in self._config["inputVar"].keys()
        }

    def _init_output_values(self):
        self._output_values = {
            k: self._config["outputVar"][k]["init"]
            for k in self._config["outputVar"].keys()
        }

    def set_input_value(self, name, new_val):
        if not self._input_values:
            return NotImplementedError("Component does not have output values.")
        self._input_values[name] = new_val

    def get_input_value(self, name):
        if not self._input_values:
            return NotImplementedError("Component does not have output values.")
        return self._input_values[name]

    def get_input_values(self):
        if not self._input_values:
            return NotImplementedError("Component does not have output values.")
        return self._input_values

    def set_input_values(self, new_val):  #
        self._input_values = new_val

    def get_output_value(self, name):
        if not self._output_values:
            return NotImplementedError("Component does not have output values.")
        return self._output_values[name]

    def set_output_value(self, name, new_val):
        if not self._output_values:
            return NotImplementedError("Component does not have output values.")
        self._output_values[name] = new_val

    def get_output_values(self):
        if not self._output_values:
            return NotImplementedError("Component does not have output values.")
        return self._output_values

    def set_output_values(self, new_val):
        if not self._output_values:
            return NotImplementedError("Component does not have output values.")
        self._output_values = new_val

    def get_node_by_name(self, name):
        if self._input_values and (name in self._config["inputVar"].keys()):
            return self._config["inputVar"][name]["nodeID"]
        elif self._output_values and (name in self._config["outputVar"].keys()):
            return self._config["outputVar"][name]["nodeID"]
        else:
            return None

    def get_name(self):
        return self._name

    def get_type(self):
        return self._config["type"]

    async def finalize(self):
        """Callback Function which is called after last do_step to finalize the component."""
        pass

    async def initialize(self):
        """Callback Function which is called before first do_step to initialize the component."""
        pass

    def contains(self, name):
        if not self._input_values and not self._output_values:
            return False

        if self._input_values and self._output_values:
            return (
                name in self._input_values.keys() or name in self._output_values.keys()
            )
        elif self._init_input_values and not self._output_values:
            return name in self._input_values.keys()
        elif not self._input_values and self._output_values:
            return name in self._output_values.keys()

    @abstractmethod
    async def do_step(self, t, dt):
        pass

    def is_finished(self):
        return self._is_finished

    def set_is_finished(self, val):
        self._is_finished = val

    def notify_simulation_finished(self):
        pass

    def create_progress_bar(self, final_time, color, desc):
        self._pbar = tqdm(
            total=final_time,
            unit="s",
            bar_format="{l_bar}{bar}| {n_fmt}{unit}/{total_fmt}{unit} [{elapsed}<{remaining}]",
            dynamic_ncols=True,
            colour=color,
            desc=desc,
        )

    def update_progress_bar(self, dt):
        if dt >= 1:
            self._pbar.update(dt)
        else:
            self._pbar_update_counter += 1
            if self._pbar_update_counter == int(1 / dt):
                self._pbar.update(1)
                self._pbar_update_counter = 0

    def log_info(self, msg):
        self._log.info(msg)

    def log_debug(self, msg):
        self._log.debug(msg)

    def log_warning(self, msg):
        self._log.warning(msg)
