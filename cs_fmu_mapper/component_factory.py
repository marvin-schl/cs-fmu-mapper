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

        # get all possible component classes
        classes = list(SimulationComponent.get_subclasses())
        master_classes = list(MasterComponent.get_subclasses())

        # map type class variable onto the component class for instantiation
        component_classes = {c.type: c for c in classes}

        # copy configuration and delete Mapping section as Mapper is no subclass of SimulationComponent
        componentConfig = config.copy()
        del componentConfig["Mapping"]

        # iterate over all components defined in the configuration
        for key in componentConfig.keys():
            # get type field from configuration of component section
            type = componentConfig[key]["type"]
            try:
                # try to find the assicated class for the defined type
                cls = component_classes[type]
                # if there is an associated class, create an instance of it. Append it to the list of components
                component_instance = cls(componentConfig[key], key)
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
                    + key
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
