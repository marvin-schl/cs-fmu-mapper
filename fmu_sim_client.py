from pyfmi import load_fmu
import pyfmi.fmi as fmi
from pyfmi.master import Master
import numpy as np
import logging
from abc import abstractmethod, ABC
import os
from utils import chooseFile
from fmpy.fmi2 import FMU2Slave
from fmpy import extract, read_model_description
from simulation_component import SimulationComponent

class FMUSimClient(SimulationComponent):

    def __init__(self, config, name):
        """Creates an instance of a FMUSimClient. This class wraps the FMU into a simulation object which can be simulated in single steps. This class
        also provides method to read the configured output values between simulation steps and write the configured input values.

        Args:
            config (dict): Section of the configuration which configures the FMU Simulation.

        Raises:
            TypeError: Is raised if the configured FMU is not compiled as Co-Simulation FMU.
        """
        super(FMUSimClient, self).__init__(config, name)
        self._log.info("Loading FMU...")
        if os.path.exists(config["path"]):
            if os.path.isfile(config["path"]):
                path = config["path"]
            elif os.path.isdir(config["path"]):
                file = chooseFile(config["path"], "FMU path is a directory. Please choose a FMU:")
                path = config["path"] + "/" + file
        else:
            raise FileNotFoundError("Scenario file not found at: " + config["path"])
        self._model = self._load_model(path)

        self._log.info("Loaded FMU successfully.")
        self._steps_per_cycle = config["numberOfStepsPerCycle"]

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
    def _read_output_valuesues(self):
        pass

    @abstractmethod
    def _call_fmu_step(self):
        pass

    def do_step(self, t, dt):
        """Triggers the configured amount of steps per cycle each 
        """
        self._log.debug("Setting FMU Input")
        self._set_input_values()
        
        
        self._log.debug("Stepping Simulation")
        
        ans = None
        for i in range(0, self._steps_per_cycle):
            self._call_fmu_step(t, dt/self._steps_per_cycle)


        self._log.debug("Reading Simulation Output.")
        self._read_output_valuesues()


    def get_total_time_per_cycle(self):
        """Returns the time in seconds which the simulation steps forward per call of do_step()-method. The time depends on the configured step size and the
        number of steps per cycle.

        Returns:
            float: Time in seconds per do_step() call.
        """
        return self._step_size*self._steps_per_cycle
    

class FMPySimClient(FMUSimClient):

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
        return FMU2Slave(guid=model_description.guid,
                        unzipDirectory=unzipdir,
                        modelIdentifier=model_description.coSimulation.modelIdentifier,
                        instanceName='instance1')

 
    def _init_model(self):
        self._time = 0
        # initialize
        self._model.instantiate()
        self._model.setupExperiment(startTime=self._time)
        self._model.enterInitializationMode()
        self._model.exitInitializationMode()

    def _set_input_values(self):
        input_vrs = list(map(lambda x: self._vrs[self.get_node_by_name(x)], self._input_values.keys()))
        self._model.setReal(input_vrs, list(self._input_values.values()))


    def _read_output_valuesues(self):
        output_keys = self._output_values.keys()
        output_vrs =  list(map(lambda x: self._vrs[self.get_node_by_name(x)], output_keys))
        val = self._model.getReal(output_vrs)
        self._output_values = dict(zip(self._output_values.keys(), val))

    def _call_fmu_step(self, t ,dt):
        self._model.doStep(currentCommunicationPoint=t, communicationStepSize=dt)

class PyFMISimClient(FMUSimClient):

    def _load_model(self, path):
        self._log.info("Using PyFMI as FMU Backend")
        model = load_fmu(path)

        if type(model) != fmi.FMUModelCS2:
            raise TypeError("FMU Model has to be defined as Co-Simulated Model.")

        return model
 
    def _init_model(self):
        self._model.initialize()

    def _set_input_values(self):
        inputNodes = list(map(lambda x: self.get_node_by_name(x), self._input_values.keys()))
        self._model.set(inputNodes, list(self._input_values.values()))

    def _read_output_valuesues(self):
        nodes = list(map(lambda x: self.get_node_by_name(x), self._output_values.keys()))
        val = map(lambda x: x[0], self._model.get(nodes))
        self._output_values = dict(zip(self._output_values.keys(), val))

    def _call_fmu_step(self, t, dt):
        self._model.do_step(t, dt, True)
