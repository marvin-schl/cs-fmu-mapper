from cs_fmu_mapper.components.simulation_component import SimulationComponent
from abc import ABC, abstractmethod


class MasterComponent(SimulationComponent):

    type = None

    def __init__(self, config, name):
        super().__init__(config, name)
        self._mapper = None
        self._t = 0
        self._timestep_per_cycle = config["timeStepPerCycle"]

    def set_mapper(self, mapper):
        self._mapper = mapper

    @abstractmethod
    async def run(self):
        pass

    async def do_step(self, t, dt):
        await self._mapper.do_step(self._t, self._timestep_per_cycle)
        self._t = self._t + self._timestep_per_cycle

    async def finalize(self):
        await self._mapper.finalize()

    def get_time(self):
        return self._t

    async def initialize(self):
        await self._mapper.initialize()
