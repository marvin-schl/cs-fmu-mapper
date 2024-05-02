from abc import ABC, abstractmethod
import logging


class SimulationComponent(ABC):

    @classmethod
    def get_subclasses(cls):
        for subclass in cls.__subclasses__():
            yield from subclass.get_subclasses()
            yield subclass

    def __init__(self, config, name):
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.info("Initializing " + str(self.__class__.__name__) + ".")
        self._config = config
        self._name = name
        self._is_finished = True

        self._input_values = None
        self._output_values = None

        if "inputVar" in self._config.keys():
            self._init_input_values()
        if "outputVar" in self._config.keys():
            self._init_output_values()

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

    def finalize(self):
        pass

    def contains(self, name):
        if self._input_values and self._output_values:
            return (
                name in self._input_values.keys() or name in self._output_values.keys()
            )
        elif self._init_input_values and not self._output_values:
            return name in self._input_values.keys()
        elif not self._input_values and self._output_values:
            return name in self._output_values.keys()

    @abstractmethod
    def do_step(self, t, dt):
        pass

    def is_finished(self):
        return self._is_finished

    def set_is_finished(self, val):
        self._is_finished = val

    def notify_simulation_finished(self):
        pass

    def log_info(self, msg):
        self._log.info(msg)

    def log_debug(self, msg):
        self._log.debug(msg)

    def log_warning(self, msg):
        self._log.warning(msg)
