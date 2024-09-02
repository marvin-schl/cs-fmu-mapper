import logging

from cs_fmu_mapper.components.master_component import MasterComponent


class OPCUAFMUMapper:

    def __init__(self, master: MasterComponent = None, component_list=[], config=None):
        """Returns an Instance of a OPCUAFMUMapper. This class is mapping the configure input and output values between different Simulation Components."""

        self._log = logging.getLogger("OPCUAFMUMapper")

        self._log.info("Initiliazing OPCUAFMUMapper...")
        self._master = master
        self._config = config

        self._pre_step_maps = self._config["preStepMappings"]
        self._post_step_maps = self._config["postStepMappings"]
        self._name_component_map = {}
        self._components = {}
        for component in component_list:
            self._components[component.get_name()] = component
        self.init_node_maps()

    def get_component_to_name(self, name):
        for component in self._components.values():
            if component.contains(name):
                return component

    def init_node_maps(self):
        names = []
        for key, value in (self._config["preStepMappings"]).items():
            names.append(key)
            names = [*names, *value]
        for key, value in (self._config["postStepMappings"]).items():
            names.append(key)
            names = [*names, *value]
        self._name_component_map = dict(
            map(lambda x: (x, self.get_component_to_name(x)), names)
        )

    def all_components_finished(self):
        """Returns True if all components are finished."""
        return all(list(map(lambda x: x.is_finished(), self._components.values())))

    def perform_mapping(self, maps: dict):
        """Maps the output values of the source component to the input values of the destination component.
        Args:
            map (dict): A dict which contains the mappings between the output values of the source component and the input values of the destination component.
        """
        for source, destinations in maps.items():
            source_component = self._name_component_map[source]
            value = source_component.get_output_value(source)
            for destination in destinations:
                dest_component = self._name_component_map[destination]
                dest_component.set_input_value(destination, value)

    async def do_step(self, t, dt):
        """Writes input values into Simulation, steps the simulation and reads the outputs of the simulation after the step is finished.
        Args:
            plc_outputs (dict): A dict which contains the nodeIDs of the PLCs output variables. The keys of the the dict are internally overwritten by the nodeID of the
            corresponding FMU input variable.


        Returns:
            dict: A dict which maps the nodeIDs of the PLCs input variables onto the corresponding output values of the FMU after the simulation step is finished.
        """

        # map pre step values
        self.perform_mapping(maps=self._pre_step_maps)

        # step all compoments which are not a plc and have a do_step method
        for component in self._components.values():
            if component != self._master:
                await component.do_step(t, dt)

        # map post step values
        self.perform_mapping(maps=self._post_step_maps)

    #        # notify plc if scenarios are finished
    #        components_finished = list(
    #            map(lambda x: x.is_finished(), self._components.values())
    #        )

    # if all(components_finished):
    #     for component in self._components.values():
    #         component.notify_simulation_finished()

    def fmu_log_callback_wrapper(self, module, level, message):
        self._log.info(message)

    async def finalize(self):
        """Finalizes the simulation and all components."""
        self._log.info("Finalizing simulation...")
        for component in self._components.values():
            if component != self._master:
                await component.finalize()
        self._log.info("Simulation finished.")
        return True

    async def initialize(self):
        """Initailizes the simulation and all components."""
        self._log.info("Initializing simulation...")
        for component in self._components.values():
            if component != self._master:
                await component.initialize()
        self._log.info("Simulation initialized.")
        return True
