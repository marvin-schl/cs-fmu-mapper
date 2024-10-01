import time

from cs_fmu_mapper.components.master_component import MasterComponent
from tqdm import tqdm


class StandaloneSimulationMaster(MasterComponent):

    type = "standalone-master"

    def __init__(self, config, name) -> None:
        super().__init__(config, name)
        self._tend = None
        if "tend" in self._config.keys():
            self._tend = self._config["tend"]
            self._is_finished = False
            self._progress = 0

    async def run(self):
        await self.initialize()

        if self._mapper is not None:
            while not self._mapper.all_components_finished():

                await self.do_step(None, None)

                if self._tend is not None:
                    self._progress = self.get_time() / self._tend

                if self._tend is not None and self.get_time() >= self._tend:
                    self._is_finished = True

        await self.finalize()
