#!/usr/bin/python
import argparse
import asyncio
import logging
import os
import sys
import warnings
from contextlib import suppress
from pathlib import Path

from cs_fmu_mapper.component_factory import ComponentFactory
from cs_fmu_mapper.config import ConfigurationBuilder
from tqdm import TqdmWarning

os.environ["FOR_DISABLE_CONSOLE_CTRL_HANDLER"] = "1"


class CSFMUMapper:
    def __init__(self, config_path, module_dir, debug=False):
        self.config_path = config_path
        self.module_dir = module_dir
        self.debug = debug
        self.setup_logging()
        self.logger = logging.getLogger("CSFMUMapper")

    def setup_logging(self):
        logging.basicConfig(
            level=logging.DEBUG if self.debug else logging.INFO,
            format="%(asctime)s  | %(name)-40s \t | %(levelname)-10s | %(message)s",
        )

        logging.getLogger("asyncua.client.ua_client.UaClient").setLevel(logging.WARNING)
        logging.getLogger("asyncua.client.client").setLevel(logging.WARNING)
        logging.getLogger("asyncua.uaprotocol").setLevel(logging.WARNING)
        logging.getLogger("asyncua.client.ua_client.UASocketProtocol").setLevel(
            logging.WARNING
        )
        warnings.filterwarnings("ignore", category=TqdmWarning)

    async def kill_tasks(self):
        pending = asyncio.all_tasks()
        for task in pending:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def run(self):
        if (
            sys.version_info[0] == 3
            and sys.version_info[1] >= 8
            and sys.platform.startswith("win")
        ):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        self.logger.info("Reading configuration file...")
        config = ConfigurationBuilder(
            config_file_path=self.config_path, module_dir=self.module_dir
        )
        if self.debug:
            config.save_to_yaml("debug_full_config.yaml")
        config = config.get_config()

        self.logger.info("Creating PLCClient, FMU Simulation and Mapper Instance...")
        master = ComponentFactory().createComponents(config)

        self.logger.info("Starting eventloop...")
        try:
            await master.run()
        except KeyboardInterrupt:
            self.logger.info("Initiating graceful exit due to KeyboardInterrupt")
            await self.kill_tasks()

        self.logger.info("Graceful exit completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OPCUA node mapping services with optional FMU simulation."
    )
    parser.add_argument(
        "-c",
        "--config_path",
        help="Path to the configuration file. Can be either a full config or a modular config.",
        type=str,
        default=Path(__file__).parent.parent / "example" / "configs" / "config.yaml",
    )
    parser.add_argument(
        "--module_dir",
        "-md",
        help="Path to the directory containing modular config files. Required if using a modular config.",
        type=str,
        default=Path(__file__).parent.parent / "example" / "configs",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save full config to debug_full_config.yaml and set logging mode to DEBUG",
    )

    args = parser.parse_args()

    mapper = CSFMUMapper(args.config_path, args.module_dir, args.debug)

    asyncio.run(mapper.run())
