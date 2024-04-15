import logging
import asyncio
from abc import ABC, abstractmethod
import asyncua.common


class AbstractOPCUAClient(ABC):
    

    def __init__(self, config, name, lock) -> None:
        """This Class implements a basic abstract OPCUA Client. Childs have to implement abstract method _run() as the operations per mapping cycle depend on the specific Client type.

        Args:
            config (dict): Configuration section of Client.
            lock (asyncio.Lock): A shared Lock object to ensure consistent read and write operations. 
        """
        self._log = logging.getLogger(self.__class__.__name__)
        self._config = config
        self._host = config["host"]
        self._port = config["port"]
        self._connection: asyncua.Client = None
        self._nodes     = {}
        self._input_val = {}
        self._output_val = {}
        self._running = False
        self._lock = lock
        self._name = name

    def get_name(self):
        """Returns the name of the client.

        Returns:
            str: Name of the client.
        """
        return self._name
    
    def get_type(self):
        return self._config["type"]
    
    def contains(self, name):
        return (name in self._input_val.keys()) or (name in self._output_val.keys())
    
    async def _connect(self):
        """Connects client to OPCUA Server if it isn't already connected.
        """
        if not self.is_connected():
            self._log.info("Connecting to Client to OPCUA server...")
            self._connection = asyncua.Client(url='opc.tcp://'+self._host+':'+self._port+'/')
            await self._connection.connect()
            self._log.info("Client connected.")
        else:
            self._log.info("Client already connected.")

    async def _disconnect(self):
        """Disconnects client from OPCUA Server if it is connected.
        """
        if self.is_connected():
            await self._connection.disconnect()
            self._log.info("Client disconnected.")
        else:
            self._log.info("Client already disconnected.")
    
    async def init_nodes(self):
        """Initialize three dicts 1 x {name : Node}, 2x{name:value} (one for inputs one for outputs)
        """
        #create input node-value dict
        for in_var in self._config["inputVar"].keys():
            #extract node object by NodeID
            input_node = self._connection.get_node(self._config["inputVar"][in_var]["nodeID"])
            self._nodes[in_var] = input_node
            #fill dict with a inital input node-value-pair
            self._input_val[in_var] = self._config["inputVar"][in_var]["init"]

        #create output node-value dict
        for out_var in self._config["outputVar"].keys():
            #extract node object by NodeID
            output_node = self._connection.get_node(self._config["outputVar"][out_var]["nodeID"])
            #fill dict with a inital output node-value-pair
            self._nodes[out_var] = output_node
            self._output_val[out_var] = self._config["outputVar"][out_var]["init"]

    async def run(self) -> None:
        """Connects client, invokes node initialization and delegates normal client operation to client specific _run() method. Disconnects and finalizes on asyncio.CancelledError. 
        """
        await self._connect()

        if not self._input_val or not self._output_val:
            await self.init_nodes() 

        self._running = True
        try:
            #delegate client specific operations to child 
            await self._run()
        except (asyncio.CancelledError, KeyboardInterrupt):
            self._log.info("Canceling OPCUA Client...")
            await self._finalize()
        await self._disconnect()
        self._log.info("OPCUA Client has been cancelled.")

    def set_input_values(self, new_val):
        """Writes new values into the input node dictionary.

        Args:
            new_val (dict): {asyncua.Node:value} dictionary containing new node values.
        """
        for input_name in new_val.keys():
            try:
                self._input_val[input_name] = new_val[input_name] 
            except KeyError:
                self._log.warning("Suppressed KeyError while setting new input values. There were keys in the new values which could not be written. Check for possible misconfiguration of node Mapping.")           

    def set_input_value(self, name, new_val):
        self._input_val[name] = new_val

    def contains(self, name):
        return (name in self._input_val.keys()) or (name in self._output_val.keys())

    def get_output_values(self):
        """Get the output value dictionary.

        Returns:
            dict: {asyncua.Node:value}-dictionary which contains output nodes as keys and their corresponding values as values.
        """
        return self._output_val
    
    def get_output_value(self, name):
        return self._output_val[name]

    def terminate(self):
        """Initiate termination without catching an exception.
        """
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
    
    async def get_node_by_name(self, name):
        """Query a asyncua.Node by it's human readable name defined in the configuration file.

        Args:
            name (str): Human readable name of a node defined in the configuration

        Raises:
            KeyError: KeyError is raised if the 'name' is not defined in the configuration.

        Returns:
            asyncua.Node: Returns the to asyncua.Node object corresponding to 'name' 
        """
        if name in self._nodes.keys():
            return self._nodes[name]
    
    @abstractmethod
    async def _run(self):
        """This method has to be implemented by every child. Periodic read of output values, periodic write of input values and any other client specific initialization and/or periodic operations have to implemented.
        """
        pass

    async def _finalize(self):
        """Invoked after asnycua.Cancelled error is catched. Overwrite by child for client specific finalization tasks.
        """
        pass

