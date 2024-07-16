# from components.simulation_component import SimulationComponent
from cs_fmu_mapper.components import *
from cs_fmu_mapper.opcua_fmu_mapper import OPCUAFMUMapper


class ComponentFactory:
    """Creates components that inherit from the SimulationComponent class and returns instances of that components with their corresponding configuration dictionary."""

    def __init__(self) -> None:
        self._components = []
        self._plc_component = None

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

        classes = list(SimulationComponent.get_subclasses())
        master_classes = list(MasterComponent.get_subclasses())

        print("Master classes: ", master_classes)

        component_classes = {c.type: c for c in classes}
        # Import custom components
        if custom_components:
            for component_class_name, component_path in custom_components.items():
                try:
                    # Add the custom component to the component_classes dictionary if it is a subclass of SimulationComponent
                    exec(f"from {component_path} import {component_class_name}")
                    component_class = eval(component_class_name)
                    if not issubclass(component_class, SimulationComponent):
                        raise Exception(
                            f"Component {component_class_name} is not a subclass of SimulationComponent."
                        )
                    component_classes[component_class.type] = component_class

                except Exception as e:
                    print(f"Error importing component {component_class_name}: {e}")

        print(list(component_classes.keys()))

        componentConfig = config.copy()
        del componentConfig["Mapping"]

        for name in componentConfig.keys():
            type = componentConfig[name]["type"]
            try:
                cls = component_classes[type]
                component_instance = cls(componentConfig[name], name)
                self._components.append(component_instance)
                if cls in master_classes and self._master_component is None:
                    self._master_component = component_instance
                elif cls in master_classes and self._master_component:
                    raise Exception("Multiple master components defined.")
            except KeyError:
                raise NotImplementedError(
                    "Defined Component "
                    + name
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
