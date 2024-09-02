import time
import numpy as np
from asyncua.ua.uatypes import VariantType
from cs_fmu_mapper.components.opcua_client import AbstractOPCUAClient
from cs_fmu_mapper.components.master_component import MasterComponent


class SynchronizedPlcClient(MasterComponent, AbstractOPCUAClient):

    type = "plc"

    def __init__(self, config, name) -> None:
        AbstractOPCUAClient.__init__(self, config, name)
        MasterComponent.__init__(self, config, name)
        self._stepNode = None
        self._finishedNode = None
        self._simulationFinishedNode = None
        self._simulationFinished = False
        self._stepNodeVal = False
        self._start_time = 0
        self._run_infinite = False
        if "runInfinite" in config:
            self._run_infinite = config["runInfinite"]
        self._k = 0
        self._n = 0
        self._s1 = 0
        self._s2 = 0
        self._exec_times = np.array([])
        self._exec_time = 0

    async def init_nodes(self):
        await super().init_nodes()
        self._stepNode = self._connection.get_node(self._config["stepNodeID"])
        self._finishedNode = self._connection.get_node(self._config["finishedNodeID"])
        self._terminateNode = self._connection.get_node(self._config["terminateNodeID"])
        self._simulationFinishedNode = self._connection.get_node(
            self._config["simulationFinishedNodeID"]
        )
        self._mapper.init_node_maps()

    async def run(self):
        await super().start()

    async def _run(self):
        await super().initialize()
        while self._running:
            curStepNodeVal = await self._stepNode.read_value()
            terminateNodeVal = await self._terminateNode.read_value()
            if terminateNodeVal:
                await self.finalize()
            elif not self._stepNodeVal and curStepNodeVal:
                await self.do_step()
            self._stepNodeVal = curStepNodeVal

            if self._mapper.all_components_finished() and not self._run_infinite:
                await self._simulationFinishedNode.write_value(
                    True, VariantType.Boolean
                )

    async def do_step(self, t=None, dt=None):
        self._start_time = time.time_ns()
        for output in self.get_output_values().keys():
            output_node = self._nodes[output]
            self.set_output_value(output, await output_node.read_value())

        await super().do_step(None, None)

        for input in self.get_input_values().keys():
            input_node = self._nodes[input]
            type = await input_node.read_data_type_as_variant_type()
            await input_node.write_value(self.get_input_value(input), type)

        await self._finishedNode.write_value(True, VariantType.Boolean)
        self._calculate_periodtime_stats()
        self._exec_time = (time.time_ns() - self._start_time) / 1000000

    def _calculate_periodtime_stats(self):
        self._exec_times = np.append(self._exec_times, [self._exec_time])
        self._k = self._k + 1
        if self._k > 10:
            self._n = self._n + 1
            self._s1 = self._s1 + self._exec_time
            self._s2 = self._s2 + self._exec_time**2
            mean = np.round(self._s1 / self._n, 2)
            std = np.round(np.sqrt(self._s2 / self._n - (self._s1 / self._n) ** 2), 2)
            if not (self._k % 1000 == 0):
                self._log.debug(
                    "Simulation execution time: mean="
                    + str(mean)
                    + "ms, std="
                    + str(std)
                    + " ms"
                )
            else:
                self._log.info(
                    "Simulation execution time: mean="
                    + str(mean)
                    + "ms, std="
                    + str(std)
                    + " ms"
                )

    async def finalize(self):
        self._running = False
        await super().finalize()
        # np.save("execution_time.npy", self._exec_times)
