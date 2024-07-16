from cs_fmu_mapper.components.master_component import MasterComponent
from tqdm import tqdm


class StandaloneSimulationMaster(MasterComponent):

    type = "standalone-master"

    def __init__(self, config, name) -> None:
        super().__init__(config, name)
        self._tend = None
        self._dt = config["timeStepPerCycle"]
        if "tend" in self._config.keys():
            self._tend = self._config["tend"]
            self._pbar = tqdm(
                total=self._tend,
                unit="s",
                bar_format="{l_bar}{bar}| {n_fmt}{unit}/{total_fmt}{unit} [{elapsed}<{remaining}]",
            )
            self._pbar_update_counter = 0

    async def run(self):
        await self.initialize()

        while not self._mapper.all_components_finished():

            await self.do_step(None, None)

            if self._tend is not None:
                self._pbar_update_counter = self._pbar_update_counter + 1
                if self._pbar_update_counter == int(1 / self._dt):
                    self._pbar.update(1)
                    self._pbar_update_counter = 0

            if self._tend is not None and self.get_time() >= self._tend:
                break

        await self.finalize()

        if self._tend is not None:
            self._pbar.close()
