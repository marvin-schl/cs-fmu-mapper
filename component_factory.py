from fmu_sim_client import FMPySimClient, PyFMISimClient
from synchronziedPlcClient import SynchronizedPlcClient
from logger import Logger
from scenario import Scenario


class ComponentFactory:

    def __init__(self) -> None:
        self._components = []
        self._plc_component = None

    def createComponents(self, config):
        self._components = []
        self._plc_component = None


        componentConfig = config.copy()
        del componentConfig["Mapping"]

        for key in componentConfig.keys():
            componentCreator = None
            if componentConfig[key]["type"] == "plc":
                componentCreator = self.addPlcComponent
            elif componentConfig[key]["type"] == "logger":
                componentCreator = self.addLoggerComponent
            elif componentConfig[key]["type"] == "scenario":
                componentCreator = self.addScenarioComponent
            elif componentConfig[key]["type"] == "fmu":
                componentCreator = self.addFmuComponent
            else:
                raise TypeError("Defined Component " + key + " of type " + componentConfig[key]["type"] + " is not valid.")
            componentCreator(config[key], key)

        return self._plc_component, self._components

    def addPlcComponent(self, config, key):
        plc = SynchronizedPlcClient(config, key)
        self._plc_component = plc

    def addLoggerComponent(self, config, key):
        logger = Logger(config, key)
        self._components.append(logger)

    def addScenarioComponent(self, config, key):
        scenario = Scenario(config, key)
        self._components.append(scenario)
                                      
    def addFmuComponent(self, config, key):
        fmu = None
        if config["backend"] == "fmpy":
            fmu = FMPySimClient(config, key)
        elif config["backend"] == "pyfmi":
            fmu = PyFMISimClient(config, key)
        self._components.append(fmu)