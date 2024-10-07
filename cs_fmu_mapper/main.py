#!/usr/bin/python
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from contextlib import suppress

import yaml
from cs_fmu_mapper.component_factory import ComponentFactory
from cs_fmu_mapper.config import ConfigurationBuilder
from cs_fmu_mapper.opcua_fmu_mapper import OPCUAFMUMapper

os.environ["FOR_DISABLE_CONSOLE_CTRL_HANDLER"] = "1"


async def kill_tasks():
    """
    Helper function to invoke asnycio.CancelledError in every running task.
    """
    pending = asyncio.all_tasks()
    for task in pending:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


# setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  | %(name)-40s \t | %(levelname)-10s | %(message)s",
)
logger = logging.getLogger("Main")

# create basic cli interface
parser = argparse.ArgumentParser(
    description="OPCUA node mapping services. Optionally starts a Modelica simulation in interactive mode via OMPython package."
)
parser.add_argument(
    "-c",
    "--config_path",
    help="Path to config file which defines OPCUA server information, node mapping and optionally Modelica simulation setup.",
    type=str,
    default=Path(__file__).parent.parent / "example" / "configs" / "config.yaml",
)

args = parser.parse_args()

logger.info("Reading configuration file...")

config = ConfigurationBuilder(config_file_path=args.config_path).get_config()

logger.info("Creating PLCClient, FMU Simualation and Mapper Instance...")
master = ComponentFactory().createComponents(config)

logger.info("Starting eventloop...")
loop = asyncio.get_event_loop()
# run asyncio task until a KeyboardInterrupt(Ctrl +C ) is catched

# necessary for graceful stopping of asyncio coroutines via Ctrl + C under Windows
if (
    sys.version_info[0] == 3
    and sys.version_info[1] >= 8
    and sys.platform.startswith("win")
):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
try:
    loop.run_until_complete(master.run())
except KeyboardInterrupt:
    logger.info("Initiating graceful exit due to KeyboardInterrupt")
    # if interrupted add kill_task coroutine to event loop
    # kill_task invokes asnycio.CancelledError in every running task so the task can finalize and terminate themselfs
    # SimulationClient should toogle 'terminate' node of modelicas OPCUA Server which then shuts down and initiates termination of Simulation
    loop.run_until_complete(kill_tasks())

loop.close()

logger.info("Graceful exit completed.")
