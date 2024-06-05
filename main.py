#!/usr/bin/python
from cs_fmu_mapper.opcua_fmu_mapper import OPCUAFMUMapper
from cs_fmu_mapper.component_factory import ComponentFactory
import asyncio
import json
import argparse
import logging
from contextlib import suppress
import yaml
import sys
import os

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


print(os.getcwd())

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
    help="Path to config.json file which defines OPCUA server information, node mapping and optionally Modelica simulation setup.",
    type=str,
    default="config.json",
)
args = parser.parse_args()

logger.info("Reading configuration file...")
f = open(args.config_path)

if args.config_path.endswith(".json"):
    logger.info("Reading JSON configuration file...")
    config = json.load(f)
elif args.config_path.endswith(".yaml") or args.config_path.endswith(".yml"):
    logger.info("Reading YAML configuration file...")
    config = yaml.load(f, Loader=yaml.FullLoader)

logger.info("Creating PLCClient, FMU Simualation and Mapper Instance...")
plcclient, component_list = ComponentFactory().createComponents(config)

if plcclient:
    # setup an sil simulation with plc as simulation master
    mapper = OPCUAFMUMapper(
        config=config["Mapping"], plc_client=plcclient, mappables=component_list
    )
    plcclient.set_mapper(mapper)

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
        loop.run_until_complete(plcclient.run())
    except KeyboardInterrupt:
        logger.info("Initiating graceful exit due to KeyboardInterrupt")
        # if interrupted add kill_task coroutine to event loop
        # kill_task invokes asnycio.CancelledError in every running task so the task can finalize and terminate themselfs
        # SimulationClient should toogle 'terminate' node of modelicas OPCUA Server which then shuts down and initiates termination of Simulation
        loop.run_until_complete(kill_tasks())

    loop.close()
else:
    # if no plc client is created this script
    mapper = OPCUAFMUMapper(
        config=config["Mapping"], plc_client=None, mappables=component_list
    )
    mapper.simulate()

logger.info("Graceful exit completed.")
