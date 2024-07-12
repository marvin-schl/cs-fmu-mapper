# from components.simulation_component import SimulationComponent
from cs_fmu_mapper.components import *
from cs_fmu_mapper.opcua_fmu_mapper import OPCUAFMUMapper


class ComponentFactory:

    def __init__(self) -> None:
        self._components = []
        self._plc_component = None

    def createComponents(self, config):
        self._components = []
        self._master_component = None

        classes = list(SimulationComponent.get_subclasses())
        master_classes = list(MasterComponent.get_subclasses())

        print(classes)
        print(master_classes)

        component_classes = {c.type: c for c in classes}

        componentConfig = config.copy()
        del componentConfig["Mapping"]

        for key in componentConfig.keys():
            type = componentConfig[key]["type"]
            try:
                cls = component_classes[type]
                component_instance = cls(componentConfig[key], key)
                self._components.append(component_instance)
                if cls in master_classes and self._master_component is None:
                    self._master_component = component_instance
                elif cls in master_classes and self._master_component:
                    raise Exception("Multiple master components defined.")
            except KeyError:
                raise NotImplementedError(
                    "Defined Component "
                    + key
                    + " of type "
                    + type
                    + " is not implemented."
                )

        if self._master_component is None:
            raise Exception("No master components defined.")

        mapper = OPCUAFMUMapper(
            config=config["Mapping"],
            master=self._master_component,
            component_list=self._components,
        )
        self._master_component.set_mapper(mapper)

        return self._master_component
