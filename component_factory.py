from fmu_sim_client import FMPySimClient, PyFMISimClient
from synchronzied_plc_client import SynchronizedPlcClient
from simulation_component import SimulationComponent
from logger import Logger
from scenario import Scenario


class ComponentFactory:

    def __init__(self) -> None:
        self._components = []
        self._plc_component = None

    def createComponents(self, config):
        self._components = []
        self._plc_component = None

        classes = list(SimulationComponent.get_subclasses())
        component_classes = {c.type: c for c in classes}

        componentConfig = config.copy()
        del componentConfig["Mapping"]

        for key in componentConfig.keys():
            type = componentConfig[key]["type"]
            try:
                cls = component_classes[type]
                self._components.append(cls(componentConfig[key], key))
                if type == "plc":
                    self._plc_component = self._components[-1]
            except KeyError:
                raise NotImplementedError("Defined Component " + key + " of type " + type + " is not implemented.")
        
        return self._plc_component, self._components
        