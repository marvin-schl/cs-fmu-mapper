# from components.simulation_component import SimulationComponent
import logging

from cs_fmu_mapper.components.master_component import MasterComponent
from cs_fmu_mapper.components.simulation_component import SimulationComponent
from cs_fmu_mapper.opcua_fmu_mapper import OPCUAFMUMapper


class ComponentFactory:
    """Creates components that inherit from the SimulationComponent class and returns instances of that components with their corresponding configuration dictionary."""

    def __init__(self) -> None:
        self._components = []
        self._plc_component = None
        self._log = logging.getLogger(self.__class__.__name__)

    def createComponents(self, config: dict) -> MasterComponent:
        """
        Creates instances of components that inherit from the SimulationComponent and MasterComponent classes with their corresponding configuration dictionaries.

        Parameters:
            config (dict): A dictionary containing the configuration for each component, including the "General" section with custom components.

        Returns:
            MasterComponent: The master component instance.
        """

        self._components = []
        self._master_component = None

        classes = list(SimulationComponent.get_subclasses())
        master_classes = list(MasterComponent.get_subclasses())

        self._log.debug("Master classes: " + str(master_classes))

        component_classes = {c.type: (c, None) for c in classes}

        # Import custom components from the "General" section of the config
        if "General" in config and "customComponents" in config["General"]:
            custom_components = config["General"]["customComponents"]
            for component_class_name, component_info in custom_components.items():
                component_path = component_info["pathToComponent"]
                try:
                    # Add the custom component to the component_classes dictionary if it is a subclass of SimulationComponent
                    exec(f"from {component_path} import {component_class_name}")
                    component_class = eval(component_class_name)
                    if not issubclass(component_class, SimulationComponent):
                        raise Exception(
                            f"Component {component_class_name} is not a subclass of SimulationComponent."
                        )
                    component_classes[component_class.type] = (  # type: ignore
                        component_class,
                        None,
                    )

                except Exception as e:
                    self._log.error(
                        f"Error importing component {component_class_name}: {e}"
                    )

        self._log.debug(list(component_classes.keys()))

        # Extract configuration sections with 'type' field declared -> presumably SimulationComponent's
        componentConfig = {name: cfg for name, cfg in config.items() if "type" in cfg}

        for name, cfg in componentConfig.items():
            if cfg["type"] == "logger":
                self._log.info(
                    "Component type 'logger' is deprecated and should be renamed to 'plotter'"
                )
                cfg["type"] = "plotter"
            type = cfg["type"]
            try:
                cls, component_input = component_classes[type]
                component_instance = cls(
                    cfg,
                    name,
                    **component_input if component_input else {},
                )
                self._components.append(component_instance)
                if cls in master_classes and self._master_component is None:
                    self._master_component = component_instance
                elif cls in master_classes and self._master_component:
                    raise Exception("Multiple master components defined.")
            except KeyError:
                raise NotImplementedError(
                    f"Defined Component {name} of type {type} is not implemented."
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
