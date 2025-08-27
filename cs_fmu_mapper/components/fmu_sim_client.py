import os
from abc import abstractmethod
import re

from fmpy import extract
from fmpy.model_description import read_model_description

# import pyfmi.fmi as fmi
from cs_fmu_mapper.components.simulation_component import SimulationComponent
from cs_fmu_mapper.utils import chooseFile
from fmpy.fmi2 import FMU2Slave
from fmpy.fmi3 import FMU3Slave

# from pyfmi import load_fmu


class FMUSimClient(SimulationComponent):

    type = None

    def __init__(self, config, name="FMUSimClient"):
        """Creates an instance of a FMUSimClient. This class wraps the FMU into a simulation object which can be simulated in single steps. This class
        also provides method to read the configured output values between simulation steps and write the configured input values.

        Args:
            config (dict): Section of the configuration which configures the FMU Simulation.
            name (str, optional): Name of the FMUSimClient. Defaults to "FMUSimClient".

        Raises:
            TypeError: Is raised if the configured FMU is not compiled as Co-Simulation FMU.
        """
        super(FMUSimClient, self).__init__(config, name)
        self._log.info("Loading FMU...")
        if os.path.exists(config["path"]):
            if os.path.isfile(config["path"]):
                path = config["path"]
            elif os.path.isdir(config["path"]):
                file = chooseFile(
                    config["path"], "FMU path is a directory. Please choose a FMU:"
                )
                path = config["path"] + "/" + file
        else:
            raise FileNotFoundError("FMU not found at: " + config["path"])
        self._fmi_version = ""
        self._model = self._load_model(path)

        self._log.info(f"Loaded FMU of version {self._fmi_version} successfully.")
        self._step_size = config["stepSize"]
        # self._steps_per_cycle = config["numberOfStepsPerCycle"]

        self._init_model()
        self._log.info("Finished Initialization of Sim Client.")

    @abstractmethod
    def _load_model(self, path):
        pass

    @abstractmethod
    def _init_model(self):
        pass

    @abstractmethod
    def _set_input_values(self):
        pass

    @abstractmethod
    def _read_output_values(self):
        pass

    @abstractmethod
    def _call_fmu_step(self):
        pass

    async def do_step(self, t: float, dt: float):
        """Triggers the configured amount of steps per cycle each

        Args:
            t (float): The current communication point (current time) of the master.
            dt (float, optional): Step size for a step including the steps per cycle. The step size for a single step is therefore dt/steps_per_cycle.
        """

        self._log.debug("Setting FMU Input")
        self._set_input_values()

        self._log.debug("Stepping Simulation")
        assert (
            dt % self._step_size == 0
        ), f"timeStepPerCycle must be a multiple of StepSize. StepSize: {self._step_size}, timeStepPerCycle: {dt}"
        t_loop = t
        for _ in range(0, int(dt / self._step_size)):
            self._call_fmu_step(t_loop, self._step_size)
            t_loop = t_loop + self._step_size

        self._log.debug("Reading Simulation Output.")
        self._read_output_values()

    def get_total_time_per_cycle(self, dt):
        """Returns the total simulation time advanced per call of the do_step() method.

        The total time depends on the configured step size and the provided dt parameter.
        It calculates the number of full steps that can be taken within dt and multiplies
        it by the step size.

        Args:
            dt (float): The desired time step for the do_step() method.

        Returns:
            float: Total simulation time in seconds advanced per do_step() call.
        """
        return self._step_size * int(dt / self._step_size)


class FMPySimClient(FMUSimClient):

    type = "fmu-fmpy"

    def _load_model(self, path):
        self._log.info("Using FMPy as FMU Backend")
        # read model description
        model_description = read_model_description(path)
        if model_description.fmiVersion.startswith("2"):
            self._fmi_version = model_description.fmiVersion
        elif model_description.fmiVersion.startswith("3"):
            self._fmi_version = model_description.fmiVersion
        else:
            raise ValueError(f"Unsupported FMI version: {model_description.fmiVersion}")
        # collect the value references
        self._vrs = {}
        for variable in model_description.modelVariables:
            self._vrs[variable.name] = {
                "valueReference": variable.valueReference,
                "variability": variable.variability,
                "causality": variable.causality,
                "type": variable.type,
                "dimensions": variable.dimensions,
            }
        # extract the FMU
        unzipdir = extract(path)

        if self._fmi_version.startswith("2"):
            return FMU2Slave(
                guid=model_description.guid,
                unzipDirectory=unzipdir,
                modelIdentifier=model_description.coSimulation.modelIdentifier,
                instanceName="instance1",
            )
        elif self._fmi_version.startswith("3"):
            return FMU3Slave(
                guid=model_description.guid,
                unzipDirectory=unzipdir,
                modelIdentifier=model_description.coSimulation.modelIdentifier,
                instanceName="instance1",
            )

    def _init_model(self):
        self._time = 0
        # initialize
        self._model.instantiate()
        if self._fmi_version.startswith("2"):
            self._model.setupExperiment(startTime=self._time)
        self._model.enterInitializationMode()
        self._model.exitInitializationMode()

    def _set_input_values(self):
        for key, val in self.get_input_values().items():
            val = self._set_fmu_value(self.get_node_by_name(key), val)

    def _read_output_values(self):
        for key in self.get_output_values().keys():
            val = self._get_fmu_value(self.get_node_by_name(key))
            self.set_output_value(key, val)

    def _call_fmu_step(self, t, dt):
        self._model.doStep(currentCommunicationPoint=t, communicationStepSize=dt)

    def _set_fmu_value(self, key: str, value: float | int | bool | str):
        """
        Set a value in the FMU. Only input variables and tunable parameters can be set. Floats, ints, booleans and strings can be set.

        Args:
            key (str): The key of the value to set.
            value (float | int | bool | str): The value to set.

        Raises:
            KeyError: If the variable is not found in the variables dictionary.
            ValueError: If the parameter is not an input or a tunable parameter.
            ValueError: If the FMU is not version 2 or 3.
            ValueError: If the type of the parameter is unknown.

        """

        if re.match(r".*\[\d+\]$", key):
            base_key = key[: key.rindex("[")]
            index = int(key[key.rindex("[") + 1 : -1]) - 1
            if base_key in self._vrs:
                if base_key not in self._vrs:
                    raise KeyError(
                        f"Variable {base_key} can not be set in FMU because it is not found in the variables dictionary"
                    )

                current_value = self._get_fmu_value(base_key)

                if (
                    self._vrs[base_key]["type"] == "Real"
                    or self._vrs[base_key]["type"] == "Float32"
                    or self._vrs[base_key]["type"] == "Float64"
                ):
                    current_value[index] = float(value)
                elif (
                    self._vrs[base_key]["type"] == "Integer"
                    or self._vrs[base_key]["type"] == "Int32"
                    or self._vrs[base_key]["type"] == "Int64"
                ):
                    current_value[index] = int(value)
                elif self._vrs[base_key]["type"] == "Boolean":
                    current_value[index] = bool(value)
                elif self._vrs[base_key]["type"] == "String":
                    current_value[index] = str(value)
                else:
                    raise ValueError(
                        f"Unknown type: {self._vrs[base_key]['type']}, can not set array element"
                    )
                value = current_value
                key = base_key

            else:

                if key not in self._vrs:
                    raise KeyError(
                        f"Variable {key} can not be set in FMU because it is not found in the variables dictionary"
                    )

                value = [value]

        else:
            value = [value]

        if key not in self._vrs:
            raise KeyError(
                f"Variable {key} can not be set in FMU because it is not found in the variables dictionary"
            )
        if (
            self._vrs[key]["causality"] != "input"
            and self._vrs[key]["variability"] != "tunable"
        ):
            raise ValueError(
                f"Parameter {key} is not an input or tunable parameter, causality: {self._vrs[key]['causality']}, variability: {self._vrs[key]['variability']}"
            )
        if not isinstance(self._model, (FMU2Slave, FMU3Slave)):
            raise ValueError(f"The FMU is not version 2 or 3")

        match self._vrs[key]["type"]:
            case "Real":
                self._model.setReal([self._vrs[key]["valueReference"]], value)
            case "Float32":
                self._model.setFloat32([self._vrs[key]["valueReference"]], value)
            case "Float64":
                self._model.setFloat64([self._vrs[key]["valueReference"]], value)
            case "Integer":
                self._model.setInteger([self._vrs[key]["valueReference"]], value)
            case "Int32":
                self._model.setInt32([self._vrs[key]["valueReference"]], value)
            case "Int64":
                self._model.setInt64([self._vrs[key]["valueReference"]], value)
            case "Boolean":
                self._model.setBoolean([self._vrs[key]["valueReference"]], value)
            case "String":
                self._model.setString([self._vrs[key]["valueReference"]], value)
            case _:
                raise ValueError(f"Unknown type: {self._vrs[key]['type']}")

    def _get_fmu_value(self, key: str) -> float | int | bool | str | list:
        """
        Get a value from the FMU. All variable types can be retrieved.

        Args:
            key (str): The key of the value to get. If the key is an array without index, the whole array is returned. If the key is an array with index, the single element is returned, e.g. "array[1]"

        Returns:
            float | int | bool | str | list: The value retrieved from the FMU.

        Raises:
            KeyError: If the variable is not found in the variables dictionary.
            ValueError: If the FMU is not version 2 or 3.
            ValueError: If the type of the parameter is unknown.
        """

        if re.match(r".*\[\d+\]$", key):
            # check if key is an array with index
            base_key = key[: key.rindex("[")]
            index = int(key[key.rindex("[") + 1 : -1]) - 1
            try:
                n_values = self._vrs[base_key]["dimensions"][0].start
                key = base_key
            except (KeyError, IndexError) as e:
                # key is not an array, but a single array element that is saved as array[index], particularly relevant for FMU 2.0 and 3.0 that do not support array dimensions
                index = 0
                n_values = 1

        elif self._vrs[key]["dimensions"]:
            # check if key is an array without index
            index = None
            n_values = self._vrs[key]["dimensions"][0].start
        else:
            # key is a single value
            index = 0
            n_values = 1

        if key not in self._vrs:
            raise KeyError(
                f"Variable {key} can not be retrieved from FMU because it is not found in the variables dictionary"
            )
        if not isinstance(self._model, (FMU2Slave, FMU3Slave)):
            raise ValueError(f"The FMU is not version 2 or 3")

        match self._vrs[key]["type"]:
            case "Real":
                if isinstance(self._model, FMU2Slave):
                    return_value = self._model.getReal(
                        vr=[self._vrs[key]["valueReference"]]
                    )
                else:
                    return_value = self._model.getReal(
                        vr=[self._vrs[key]["valueReference"]], nValues=n_values
                    )
            case "Float32":
                if isinstance(self._model, FMU2Slave):
                    return_value = self._model.getFloat32(
                        vr=[self._vrs[key]["valueReference"]]
                    )
                else:
                    return_value = self._model.getFloat32(
                        vr=[self._vrs[key]["valueReference"]], nValues=n_values
                    )
            case "Float64":
                if isinstance(self._model, FMU2Slave):
                    return_value = self._model.getFloat64(
                        vr=[self._vrs[key]["valueReference"]]
                    )
                else:
                    return_value = self._model.getFloat64(
                        vr=[self._vrs[key]["valueReference"]], nValues=n_values
                    )
            case "Integer":
                if isinstance(self._model, FMU2Slave):
                    return_value = self._model.getInteger(
                        vr=[self._vrs[key]["valueReference"]]
                    )
                else:
                    return_value = self._model.getInteger(
                        vr=[self._vrs[key]["valueReference"]], nValues=n_values
                    )
            case "Int32":
                if isinstance(self._model, FMU2Slave):
                    return_value = self._model.getInt32(
                        vr=[self._vrs[key]["valueReference"]]
                    )
                else:
                    return_value = self._model.getInt32(
                        vr=[self._vrs[key]["valueReference"]], nValues=n_values
                    )
            case "Int64":
                if isinstance(self._model, FMU2Slave):
                    return_value = self._model.getInt64(
                        vr=[self._vrs[key]["valueReference"]]
                    )
                else:
                    return_value = self._model.getInt64(
                        vr=[self._vrs[key]["valueReference"]], nValues=n_values
                    )
            case "Boolean":
                if isinstance(self._model, FMU2Slave):
                    return_value = self._model.getBoolean(
                        vr=[self._vrs[key]["valueReference"]]
                    )
                else:
                    return_value = self._model.getBoolean(
                        vr=[self._vrs[key]["valueReference"]], nValues=n_values
                    )
            case "String":
                if isinstance(self._model, FMU2Slave):
                    return_value = self._model.getString(
                        vr=[self._vrs[key]["valueReference"]]
                    )
                else:
                    return_value = self._model.getString(
                        vr=[self._vrs[key]["valueReference"]], nValues=n_values
                    )
            case _:
                raise ValueError(f"Unknown type: {self._vrs[key]['type']}")

        if index is not None:
            return_value = return_value[index]

        return return_value


# class PyFMISimClient(FMUSimClient):
#
#    type = "fmu-pyfmi"
#
#    def _load_model(self, path):
#        self._log.info("Using PyFMI as FMU Backend")
#        model = load_fmu(path)
#
#        if type(model) != fmi.FMUModelCS2:
#            raise TypeError("FMU Model has to be defined as Co-Simulated Model.")
#        self._fmi_version = "2.0"
#        return model
#
#    def fmu_log_callback_wrapper(self, module, level, message):
#        self._log.info(message)
#
#    def _init_model(self):
#        self._model.set_additional_logger(self.fmu_log_callback_wrapper)
#        self._model.initialize()
#
#    def _set_input_values(self):
#        for key, val in self.get_input_values().items():
#            self._model.set(self.get_node_by_name(key), val)
#
#    def _read_output_values(self):
#        for key in self.get_output_values().keys():
#            val = self._model.get(self.get_node_by_name(key))
#            self.set_output_value(key, val[0])
#
#    def _call_fmu_step(self, t, dt):
#        self._model.do_step(t, dt, True)
