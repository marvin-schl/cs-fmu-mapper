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

class FMUSimClient(ABC):

    def __init__(self, config, name):
        """Creates an instance of a FMUSimClient. This class wraps the FMU into a simulation object which can be simulated in single steps. This class
        also provides method to read the configured output values between simulation steps and write the configured input values.

        Args:
            config (dict): Section of the configuration which configures the FMU Simulation.

        Raises:
            TypeError: Is raised if the configured FMU is not compiled as Co-Simulation FMU.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Initializing Sim Client...")
        self._config = config
        self._name = name
        self._logger.info("Loading FMU...")
        if os.path.exists(config["path"]):
            if os.path.isfile(config["path"]):
                path = config["path"]
            elif os.path.isdir(config["path"]):
                file = chooseFile(config["path"], "FMU path is a directory. Please choose a FMU:")
                path = config["path"] + "/" + file
        else:
            raise FileNotFoundError("Scenario file not found at: " + config["path"])
        self._model = self._load_model(path)

        self._logger.info("Loaded FMU successfully.")
        self._steps_per_cycle = config["numberOfStepsPerCycle"]
        self._input_val = dict(map(lambda x: (x, config["inputVar"][x]["init"]), config["inputVar"].keys()))
        self._output_val = dict(map(lambda x: (x,config["outputVar"][x]["init"]), config["outputVar"].keys()))

        self._init_model()
        self._logger.info("Finished Initialization of Sim Client.")


    def get_name(self):
        """Returns the name of the FMU.

        Returns:
            str: Name of the FMU.
        """
        return self._name
    
    def contains(self, name):
        return (name in self._input_val.keys()) or (name in self._output_val.keys())
    
    def finalize(self):
        pass
    
    def get_type(self):
        return self._config["type"]

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

    def do_step(self, t, dt):
        """Triggers the configured amount of steps per cycle each 
        """
        self._logger.debug("Setting FMU Input")
        self._set_input_values()
        
        
        self._logger.debug("Stepping Simulation")
        
        ans = None
        for i in range(0, self._steps_per_cycle):
            self._call_fmu_step(t, dt/self._steps_per_cycle)


        self._logger.debug("Reading Simulation Output.")
        self._read_output_values()


    def get_node_by_name(self, name):
        """Queries a configured input or output variable of the FMU by the configured name.

        Args:
            name (str): Name of the desired FMU variable as configured.

        Raises:
            KeyError: Is raised if the queried name is neither configured as input nor as output variable.

        Returns:
            str: The ID from which the queried variable is accessible inside the FMU.
        """
        if name in self._config["inputVar"].keys():
            nodeID = self._config["inputVar"][name]["nodeID"]
        elif name in self._config["outputVar"].keys():
            nodeID =self._config["outputVar"][name]["nodeID"]
        else:
            raise KeyError("Node " + name + " not defined in config.")
        return nodeID
    
    def set_input_values(self, new_val):
        """Writes the configured input values. The method iterates over each element in new_val and updates the corresponding value of the internal
        input variable. If there is a key in new_val which does not correspond to an internal variable then a Warning is printed an the element will be skipped.

        Args:
            new_val (dict): A dict which maps the configured nodeIDs of a input Variable onto the new Value.
        """
        for name in new_val:
            try:
                self._input_val[name] = new_val[name] 
            except KeyError:
                self._log.warning("Suppressed KeyError while setting new input values. There were keys in the new values which could not be written. Check for possible misconfiguration of node Mapping.")           
    
    def set_input_value(self, name, value):
        self._input_val[name] = value

    def get_output_values(self):
        """Returns the configured output Variables.

        Returns:
            dict: A dict which maps the configured nodeIDs of a output Variable onto it's current Value.
        """
        return self._output_val
    
    def get_output_value(self, name):
        return self._output_val[name]

    def get_total_time_per_cycle(self):
        """Returns the time in seconds which the simulation steps forward per call of do_step()-method. The time depends on the configured step size and the
        number of steps per cycle.

        Returns:
            float: Time in seconds per do_step() call.
        """
        return self._step_size*self._steps_per_cycle
    
    def contains(self, name):
        return (name in self._input_val.keys()) or (name in self._output_val.keys())

class FMPySimClient(FMUSimClient):

    def _load_model(self, path):
        self._logger.info("Using FMPy as FMU Backend")
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
        input_vrs = list(map(lambda x: self._vrs[self.get_node_by_name(x)], self._input_val.keys()))
        self._model.setReal(input_vrs, list(self._input_val.values()))


    def _read_output_values(self):
        output_keys = self._output_val.keys()
        output_vrs =  list(map(lambda x: self._vrs[self.get_node_by_name(x)], output_keys))
        val = self._model.getReal(output_vrs)
        self._output_val = dict(zip(self._output_val.keys(), val))

    def _call_fmu_step(self, t ,dt):
        self._model.doStep(currentCommunicationPoint=t, communicationStepSize=dt)

class PyFMISimClient(FMUSimClient):

    def _load_model(self, path):
        self._logger.info("Using PyFMI as FMU Backend")
        model = load_fmu(path)

        if type(model) != fmi.FMUModelCS2:
            raise TypeError("FMU Model has to be defined as Co-Simulated Model.")

        return model
 
    def _init_model(self):
        self._model.initialize()

    def _set_input_values(self):
        inputNodes = list(map(lambda x: self.get_node_by_name(x), self._input_val.keys()))
        self._model.set(inputNodes, list(self._input_val.values()))

    def _read_output_values(self):
        nodes = list(map(lambda x: self.get_node_by_name(x), self._output_val.keys()))
        val = map(lambda x: x[0], self._model.get(nodes))
        self._output_val = dict(zip(self._output_val.keys(), val))

    def _call_fmu_step(self, t, dt):
        self._model.do_step(t, dt, True)
