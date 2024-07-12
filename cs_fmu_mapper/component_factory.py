# from components.simulation_component import SimulationComponent
from cs_fmu_mapper.components import *


class ComponentFactory:

    def __init__(self) -> None:
        self._components = []
        self._plc_component = None

    def createComponents(self, config):
        self._components = []
        self._plc_component = None

        classes = list(SimulationComponent.get_subclasses())
        print(classes)
        component_classes = {c.type: c for c in classes}

        componentConfig = config.copy()
        del componentConfig["Mapping"]

        for key in componentConfig.keys():
            type = componentConfig[key]["type"]
            try:
                cls = component_classes[type]
                component_instance = cls(componentConfig[key], key)
                self._components.append(component_instance)
                if type == "plc":
                    self._plc_component = self._components[-1]
            except KeyError:
                raise NotImplementedError(
                    "Defined Component "
                    + key
                    + " of type "
                    + type
                    + " is not implemented."
                )

        return self._plc_component, self._components
