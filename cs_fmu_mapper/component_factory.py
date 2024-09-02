# from components.simulation_component import SimulationComponent
import logging

from cs_fmu_mapper.components import *
from cs_fmu_mapper.opcua_fmu_mapper import OPCUAFMUMapper


class ComponentFactory:
    """Creates components that inherit from the SimulationComponent class and returns instances of that components with their corresponding configuration dictionary."""

    def __init__(self) -> None:
        self._components = []
        self._plc_component = None
        self._log = logging.getLogger(self.__class__.__name__)

    def createComponents(
        self, config: dict, custom_components: dict[str, str] = {}
    ) -> MasterComponent:
        """
        Creates instances of components that inherit from the SimulationComponent and MasterComponent classes with their corresponding configuration dictionaries.

        Parameters:
            config (dict): A dictionary containing the configuration for each component.
            custom_components (dict): An optional dictionary where keys are the class names and values are importing paths to the Python files defining the custom components. Example of a custom component: {"Algorithm": "Module.submodule"} where the custom component "Algorithm" is defined in the file "submodule.py" in the "Module" directory.

        Returns:
            MasterComponent: The master component instance.
        """

        self._components = []
        self._master_component = None

        # get all possible component classes
        classes = list(SimulationComponent.get_subclasses())
        master_classes = list(MasterComponent.get_subclasses())

        print(classes)
        print(master_classes)

        component_classes = {c.type: c for c in classes}

        # copy configuration and delete Mapping section as Mapper is no subclass of SimulationComponent
        componentConfig = config.copy()
        del componentConfig["Mapping"]

        for name in componentConfig.keys():
            type = componentConfig[name]["type"]
            try:
                cls, component_input = component_classes[type]
                component_instance = cls(
                    componentConfig[name],
                    name,
                    **component_input if component_input else {},
                )
                self._components.append(component_instance)

                # check if the component is a master component
                if cls in master_classes and self._master_component is None:
                    # if so set the master component
                    self._master_component = component_instance
                elif cls in master_classes and self._master_component:
                    # if it is a master component and there is already a master component defined, raise an exception
                    # only a single simulation master can exist
                    raise Exception("Multiple master components defined.")
            except KeyError:
                # raise an exception if the specified type in the configartion can not be associated with a SimulationComponent subclass
                raise NotImplementedError(
                    "Defined Component "
                    + name
                    + " of type "
                    + type
                    + " is not implemented."
                )

        # rase an exception if no master component is defined => there has to be exactly one master component
        if self._master_component is None:
            raise Exception("No master components defined.")

        # create the mapper with it's configuation and all instantiated components
        mapper = OPCUAFMUMapper(
            config=config["Mapping"],
            master=self._master_component,
            component_list=self._components,
        )
        self._master_component.set_mapper(mapper)

        # return the master component as this is the entry point for the simulation
        return self._master_component
