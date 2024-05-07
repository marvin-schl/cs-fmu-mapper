import asyncio
from components.simulation_component import SimulationComponent
import asyncua.common


class ExternalOPCUAClient(SimulationComponent):
    type = "external_opcua_client"

    def __init__(
        self, config: dict, name: str, stop_time: int, lock: asyncio.Lock = None
    ) -> None:
        """This Class implements a basic abstract OPCUA Client that allows to connect to an external OPCUA client.

        Args:
            config (dict): Configuration section of Client.
            lock (asyncio.Lock): A shared Lock object to ensure consistent read and write operations.
            stop_time (int): The time in seconds after which the simulation should be terminated.
        """
        super(ExternalOPCUAClient, self).__init__(config, name)
        self._host = config["host"]
        self._port = config["port"]
        self._steps_per_cycle = config["numberOfStepsPerCycle"]
        self._step_node_name = config["stepNodeName"]
        self._terminate_node_name = config["terminateNodeName"]
        self._run_node_name = config["runNodeName"]
        self._enable_stop_time_node_name = config["enableStopTimeNodeName"]
        self._time_node_name = config["timeNodeName"]
        self._stop_time = stop_time
        self._connection: asyncua.Client = None
        self._nodes = {}
        self._running = False
        self._lock = lock
        self._names_id_map = {}

    async def _connect(self):
        """Connects client to OPCUA Server if it isn't already connected."""
        if not self.is_connected():
            self._log.info("Connecting to Client to OPCUA server...")
            self._connection = asyncua.Client(
                url="opc.tcp://" + self._host + ":" + self._port + "/"
            )
            await self._connection.connect()
            self._log.info("Client connected.")
        else:
            self._log.info("Client already connected.")

    async def _disconnect(self):
        """Disconnects client from OPCUA Server if it is connected."""
        if self.is_connected():
            await self._connection.disconnect()
            self._log.info("Client disconnected.")
        else:
            self._log.info("Client already disconnected.")

    async def set_enable_stop_time(self, enable_stop_time: bool):
        """Set the enableStopTime node to the given value.

        Args:
            enable_stop_time (bool): Value to set the enableStopTime node to.
        """
        enable_stop_time_node = self._connection.get_node(
            self._names_id_map[self._enable_stop_time_node_name]
        )
        await enable_stop_time_node.write_value(
            enable_stop_time, asyncua.ua.uatypes.VariantType.Boolean
        )

    async def get_enable_stop_time(self) -> bool:
        """Read the value of the enableStopTime node.

        Returns:
            bool: Value of the enableStopTime node.
        """
        enable_stop_time_node = self._connection.get_node(
            self._names_id_map[self._enable_stop_time_node_name]
        )
        return await enable_stop_time_node.read_value()

    async def get_time(self) -> float:
        """Read the value of the time node.

        Returns:
            float: Value of the time node.
        """
        time_node = self._connection.get_node(self._names_id_map[self._time_node_name])
        return await time_node.read_value()

    async def terminate(self):
        """Initiate termination without catching an exception."""
        print("Terminating OPCUA Client...")
        self._log.info("Terminating OPCUA Client...")
        terminate_node = self._connection.get_node(
            self._names_id_map[self._terminate_node_name]
        )
        await terminate_node.write_value(True, asyncua.ua.uatypes.VariantType.Boolean)
        print("Simulation terminated.")

    def is_connected(self):
        """Check if Client is connected.

        Returns:
            bool: return true if client is connected, false if client is not connected
        """
        if self._connection == None:
            return False
        elif self._connection.uaclient.protocol == None:
            return False
        elif self._connection.uaclient.protocol.state == "open":
            return True
        else:
            print(self._connection.uaclient.protocol.state)
            return False

    async def _map_nodeIDs_to_nodeNames(self, node_names: list[str]) -> dict[str, str]:
        """Create a map where each a nodeID is mapped to a list of given node names (browse names). This is important because usually the browse name
        of the node is known but the nodeID is needed to access the node on the OPCUA server. NodeIDs are formatted as for example "ns=1;i=1001",
        where "ns=1" is referred to the NamespaceIndex and "i=1001" as Identifier. The browse name is the name of the node, e.g. "room1.temperature".

        Args:
            node_names (list[str]): List of node names to map to nodeIDs.

        Returns:
            dict: Dictionary with browse names as keys and nodeIDs as values.
        """

        node_List = await asyncua.common.ua_utils.get_node_children(
            self._connection.nodes.objects
        )
        browse_names = []
        node_ids = []
        for node in node_List:
            browse_name = (await node.read_browse_name()).Name
            identifier = node.nodeid.Identifier
            namespace_index = node.nodeid.NamespaceIndex
            if browse_name in node_names:
                node_id = f"ns={namespace_index};i={identifier}"
                browse_names.append(browse_name)
                node_ids.append(node_id)
        return {k: v for k, v in zip(browse_names, node_ids)}

    async def connect(self):
        """Connect to OPCUA Server and initialize node maps."""

        self._log.info("Connecting to OPCUA Client...")
        await self._connect()

        # Create a mappping of node names (inputs, outputs, utility nodes) to node IDs
        input_values_node_names = [
            self.get_node_by_name(name) for name in self.get_input_values().keys()
        ]
        output_values_node_names = [
            self.get_node_by_name(name) for name in self.get_output_values().keys()
        ]
        all_node_names = input_values_node_names + output_values_node_names

        # add utility nodes to input values
        all_node_names.append(self._step_node_name)
        all_node_names.append(self._terminate_node_name)
        all_node_names.append(self._run_node_name)
        all_node_names.append(self._enable_stop_time_node_name)
        all_node_names.append(self._time_node_name)

        self._names_id_map = await self._map_nodeIDs_to_nodeNames(all_node_names)

        print(f"Connection established with OPCUA Server at {self._host}:{self._port}")
        print(
            f"Node initialization completed with mapping from names to node IDs as follows: {self._names_id_map}"
        )

    async def run(self) -> None:
        try:
            await self._step()
        except (asyncio.CancelledError, KeyboardInterrupt):
            self._log.info("Canceling OPCUA Client...")
            await self._finalize()
        await self._disconnect()
        self._log.info("OPCUA Client has been cancelled.")

    async def _do_single_step(self):
        """Perform a single step of the simulation. The step_size is determined by the external OPCUA server."""
        step_node = self._connection.get_node(self._names_id_map[self._step_node_name])
        await step_node.write_value(True, asyncua.ua.uatypes.VariantType.Boolean)

    async def do_step(self, t=None, dt=None):
        """Perform a simulation step. One step consists of multiple single steps, where the number of single steps is described by the steps_per_cycle class attribute.
        The time for each step is determined by the external OPCUA server. Prior to performing the steps, the input values are set and after the steps the output values are read.

        Args:
            t : Not used.
            dt : Not used.
        """

        assert self.is_connected(), "Client is not connected to OPCUA Server."

        await self.set_enable_stop_time(False)

        self._log.debug("Setting FMU Input")
        await self._set_input_values()

        print("--------------------Do Step------------------------")
        self._log.debug("Stepping Simulation")
        print(f"Performing {self._steps_per_cycle} steps per cycle.")

        for _ in range(0, self._steps_per_cycle):
            print("Single Step")
            await self._do_single_step()

        await self._read_output_values()

        if await self.get_time() >= self._stop_time:
            await self.set_enable_stop_time(True)
            await self.terminate()
            await self._disconnect()

    async def _set_input_values(self):
        """Set input values from class attribute to OPCUA server."""
        for key, val in self.get_input_values().items():
            node_name = self.get_node_by_name(key)
            node = self._connection.get_node(self._names_id_map[node_name])
            self._log.debug(
                f"Set Node with name '{key}' and node id '{self._names_id_map[node_name]}' to value '{val}'"
            )
            await node.write_value(val, asyncua.ua.uatypes.VariantType.Float)

    async def _read_output_values(self):
        """Read output values from OPCUA server and set them to class attribute."""
        for key in self.get_output_values().keys():
            node_name = self.get_node_by_name(key)
            node = self._connection.get_node(self._names_id_map[node_name])
            val = await node.read_value()
            self._output_values[key] = val
            self._log.debug(
                f"Read value '{val}' from node '{node_name}' with node id '{self._names_id_map[node_name]}'"
            )

    async def _finalize(self):
        """Invoked after asnycua.Cancelled error is catched. Overwrite by child for client specific finalization tasks."""
        pass
