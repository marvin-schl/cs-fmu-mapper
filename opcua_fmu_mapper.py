from components.synchronzied_plc_client import SynchronizedPlcClient
import logging


class OPCUAFMUMapper:

    def __init__(
        self, plc_client: SynchronizedPlcClient = None, mappables=[], config=None
    ):
        """Returns an Instance of a OPCUAFMUMapper. This class is mapping the configure input and output values between FMU and PLC.

        Args:
            plc_client (SynchronizedPlcClient): A instance of SynchronizedPlcClient which connect to the internal OPCUA Server of the PLC.
            sim_client (FMUSimClient):          A instance of FMUSimClient.
            config (_type_):                    Section of the configuration File which describes the mapping between input and outputs of FMU and PLC.
        """

        self._log = logging.getLogger("OPCUAMapper")

        self._log.info("Initiliazing OPCUA Mapper...")
        self._plc_client = plc_client
        self._config = config

        self._pre_step_maps = self._config["preStepMappings"]
        self._post_step_maps = self._config["postStepMappings"]
        self._name_component_map = {}
        self._timestep_per_cycle = self._config["timeStepPerCycle"]
        self._components = {}
        self._t = 0

        if plc_client:
            component_list = [plc_client, *mappables]
            self._plc_client.set_time_per_cycle(self._timestep_per_cycle)
        else:
            component_list = mappables

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

    def simulate(self):
        scenarios = list(
            filter(lambda x: x.get_type() == "scenario", self._components.values())
        )
        scenario_states = list(map(lambda x: x.is_finished(), scenarios))
        while not all(scenario_states):
            self.do_step()
            scenario_states = list(map(lambda x: x.is_finished(), scenarios))
        self.finalize()

    def do_step(self):
        """Writes input values into Simulation, steps the simulation and reads the outputs of the simulation after the step is finished.
        Args:
            plc_outputs (dict): A dict which contains the nodeIDs of the PLCs output variables. The keys of the the dict are internally overwritten by the nodeID of the
            corresponding FMU input variable.


        Returns:
            dict: A dict which maps the nodeIDs of the PLCs input variables onto the corresponding output values of the FMU after the simulation step is finished.
        """
        # increment time

        for source, destinations in self._pre_step_maps.items():
            source_component = self._name_component_map[source]
            value = source_component.get_output_value(source)
            for destination in destinations:
                dest_component = self._name_component_map[destination]
                dest_component.set_input_value(destination, value)

        # step all compoments which are not a plc and have a do_step method
        for component in self._components.values():
            if component.get_type() != "plc":
                component.do_step(self._t, self._timestep_per_cycle)

        for source, destinations in self._post_step_maps.items():
            source_component = self._name_component_map[source]
            value = source_component.get_output_value(source)
            for destination in destinations:
                dest_component = self._name_component_map[destination]
                dest_component.set_input_value(destination, value)

        # notify plc if scenarios are finished
        components_finished = list(
            map(lambda x: x.is_finished(), self._components.values())
        )
        if all(components_finished):
            for component in self._components.values():
                component.notify_simulation_finished()

        self._t = self._t + self._timestep_per_cycle

    def fmu_log_callback_wrapper(self, module, level, message):
        self._log.info(message)

    def finalize(self):
        """Finalizes the simulation and all components."""
        self._log.info("Finalizing simulation...")
        for component in self._components.values():
            if component.get_type() != "plc":
                component.finalize()
        self._log.info("Simulation finished.")
        return True
