from abc import ABC, abstractmethod

from cs_fmu_mapper.components.simulation_component import SimulationComponent
from tqdm import tqdm


class MasterComponent(SimulationComponent):

    type = None

    def __init__(self, config, name):
        super().__init__(config, name)
        self._mapper = None
        self._t = 0
        self._pbar = None
        self._timestep_per_cycle = config["timeStepPerCycle"]
        self._prev_progress = 0

    def set_mapper(self, mapper):
        self._mapper = mapper

    def create_progress_bar(self, color, desc):
        self._pbar = tqdm(
            total=100,
            unit="%",
            bar_format="{l_bar}{bar}| {n:.2f}{unit}/{total:.2f}{unit} [{elapsed}<{remaining}]",
            dynamic_ncols=True,
            colour=color,
            desc=desc,
        )

    def update_progress_bar(self, finished=False):
        if self._pbar is None:
            return

        if finished:
            # ensure that progressbar ends at 100%
            self._pbar.update((1 - self._prev_progress) * 100)
            self._pbar.refresh()
            self._pbar.close()
            return

        progress = min(max(0, min([self.get_progress(), self._mapper.get_progress()])), 1)
        if (progress - self._prev_progress) * 100 >= 1:
            self._pbar.update(round((progress - self._prev_progress) * 100, 4))
            self._prev_progress = progress
            self._pbar.refresh()

    @abstractmethod
    async def run(self):
        pass

    async def do_step(self, t, dt):
        self.update_progress_bar()
        if self._mapper is not None:
            await self._mapper.do_step(self._t, self._timestep_per_cycle)
        self._t = self._t + self._timestep_per_cycle

    async def finalize(self):
        self.update_progress_bar(finished=True)
        if self._mapper is not None:
            await self._mapper.finalize()

    def get_time(self):
        return self._t

    async def initialize(self):
        if self._mapper is not None:
            await self._mapper.initialize()
        self.create_progress_bar("green", "Simulation")
