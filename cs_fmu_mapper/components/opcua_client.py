import logging
import asyncio
from abc import ABC, abstractmethod
import asyncua.common

# from simulation_component import SimulationComponent


class AbstractOPCUAClient(ABC):

    def __init__(self, config, name, lock=None) -> None:
        """This Class implements a basic abstract OPCUA Client. Childs have to implement abstract method _run() as the operations per mapping cycle depend on the specific Client type.

        Args:
            config (dict): Configuration section of Client.
            lock (asyncio.Lock): A shared Lock object to ensure consistent read and write operations.
        """
        self._host = config["host"]
        self._port = config["port"]
        self._connection: asyncua.Client = None
        self._nodes = {}
        self._running = False
        self._lock = lock

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

    async def init_nodes(self):
        """Initialize three dicts 1 x {name : Node}, 2x{name:value} (one for inputs one for outputs)"""
        # create input node-value dict
        for in_var in self._config["inputVar"].keys():
            # extract node object by NodeID
            input_node = self._connection.get_node(
                self._config["inputVar"][in_var]["nodeID"]
            )
            self._nodes[in_var] = input_node
            # fill dict with a inital input node-value-pair
            self._input_values[in_var] = self._config["inputVar"][in_var]["init"]

        # create output node-value dict
        for out_var in self._config["outputVar"].keys():
            # extract node object by NodeID
            output_node = self._connection.get_node(
                self._config["outputVar"][out_var]["nodeID"]
            )
            # fill dict with a inital output node-value-pair
            self._nodes[out_var] = output_node
            self._output_values[out_var] = self._config["outputVar"][out_var]["init"]

    async def start(self) -> None:
        """Connects client, invokes node initialization and delegates normal client operation to client specific simulate() method. Disconnects and finalizes on asyncio.CancelledError."""
        await self._connect()

        if not self._nodes:
            await self.init_nodes()

        self._running = True
        try:
            # delegate client specific operations to child
            await self._run()
        except (asyncio.CancelledError, KeyboardInterrupt):
            self._log.info("Canceling OPCUA Client...")
            await self.finalize()
        await self._disconnect()
        self._log.info("OPCUA Client has been cancelled.")

    def terminate(self):
        """Initiate termination without catching an exception."""
        self._running = False

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

    @abstractmethod
    async def _run(self):
        """This method has to be implemented by every child. Periodic read of output values, periodic write of input values and any other client specific initialization and/or periodic operations have to implemented."""
        pass

    async def finalize(self):
        """Invoked after asnycua.Cancelled error is catched. Overwrite by child for client specific finalization tasks."""
        pass
