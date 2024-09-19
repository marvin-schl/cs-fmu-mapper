import logging
import os
from abc import ABC, abstractmethod

import numpy as np
import pyfmi.fmi as fmi
from cs_fmu_mapper.components.simulation_component import SimulationComponent
from cs_fmu_mapper.utils import chooseFile
from fmpy import extract, read_model_description
from fmpy.fmi2 import FMU2Slave
from pyfmi import load_fmu
from pyfmi.master import Master


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
        self._model = self._load_model(path)

        self._log.info("Loaded FMU successfully.")
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
        # collect the value references
        self._vrs = {}
        for variable in model_description.modelVariables:
            self._vrs[variable.name] = variable.valueReference
        # extract the FMU
        unzipdir = extract(path)
        return FMU2Slave(
            guid=model_description.guid,
            unzipDirectory=unzipdir,
            modelIdentifier=model_description.coSimulation.modelIdentifier,
            instanceName="instance1",
        )

    def _init_model(self):
        self._time = 0
        # initialize
        self._model.instantiate()
        self._model.setupExperiment(startTime=self._time)
        self._model.enterInitializationMode()
        self._model.exitInitializationMode()

    def _set_input_values(self):
        for key, val in self.get_input_values().items():
            self._model.setReal([self._vrs[self.get_node_by_name(key)]], [val])

    def _read_output_values(self):
        for key in self.get_output_values().keys():
            val = self._model.getReal([self._vrs[self.get_node_by_name(key)]])
            self.set_output_value(key, val[0])

    def _call_fmu_step(self, t, dt):
        self._model.doStep(currentCommunicationPoint=t, communicationStepSize=dt)


class PyFMISimClient(FMUSimClient):

    type = "fmu-pyfmi"

    def _load_model(self, path):
        self._log.info("Using PyFMI as FMU Backend")
        model = load_fmu(path)

        if type(model) != fmi.FMUModelCS2:
            raise TypeError("FMU Model has to be defined as Co-Simulated Model.")

        return model

    def fmu_log_callback_wrapper(self, module, level, message):
        self._log.info(message)

    def _init_model(self):
        self._model.set_additional_logger(self.fmu_log_callback_wrapper)
        self._model.initialize()

    def _set_input_values(self):
        for key, val in self.get_input_values().items():
            self._model.set(self.get_node_by_name(key), val)

    def _read_output_values(self):
        for key in self.get_output_values().keys():
            val = self._model.get(self.get_node_by_name(key))
            self.set_output_value(key, val[0])

    def _call_fmu_step(self, t, dt):
        self._model.do_step(t, dt, True)
