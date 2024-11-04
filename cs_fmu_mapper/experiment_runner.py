"""
A general-purpose experiment runner that executes experiments defined in YAML configuration files.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
import argparse

import yaml
from cs_fmu_mapper.config import ConfigurationBuilder
from cs_fmu_mapper.main import CSFMUMapper


class ExperimentRunner:
    """
    A class to manage and run experiments defined in YAML configuration files.
    """

    def __init__(
        self,
        base_config: Path,
        module_dir: Path,
        experiments_dir: Path,
        experiments_file: str = "experiments.yaml",
        run_file: str = "run.yaml",
        temp_dir: str = "temp",
        debug: bool = False,
    ):
        """
        Initialize the ExperimentRunner.

        ### Args:
        - ` base_config` (Path): Path to the base configuration file
        - `module_dir` (Path): Path to the directory containing module configurations
        - `experiments_dir` (Path): Path to the directory containing experiment files
        - `experiments_file` (str, optional): Name of the experiments definition file. Defaults to "experiments.yaml".
        - `run_file` (str, optional): Name of the run configuration file. Defaults to "run.yaml".
        - `temp_dir` (str, optional): Name of temporary directory for generated configs. Defaults to "temp".
        - `debug` (bool, optional): Enable debug logging. Defaults to False.
        """
        self.base_config = Path(base_config)
        self.module_dir = Path(module_dir)
        self.experiments_dir = Path(experiments_dir)
        self.experiments_file = experiments_file
        self.run_file = run_file
        self.temp_dir = self.experiments_dir / temp_dir
        self.debug = debug

        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging settings."""
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
        )

    @staticmethod
    def load_yaml_file(file_path: Path) -> Dict[str, Any]:
        """
        Load and return the contents of a YAML file.

        ### Args:
        - `file_path` (Path): Path to the YAML file

        ### Returns:
        - `Dict[str, Any]`: Parsed YAML content
        """
        with open(file_path, "r") as file:
            return yaml.safe_load(file)

    def _create_temp_directory(self) -> None:
        """Create temporary directory for experiment configurations."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _get_experiments(self) -> Dict[str, Dict[str, Any]]:
        """
        Load and filter experiments based on run configuration.

        ### Returns:
        - `Dict[str, Dict[str, Any]]`: Dictionary of experiment configurations
        """
        run_config = self.load_yaml_file(self.experiments_dir / self.run_file)
        all_experiments = self.load_yaml_file(
            self.experiments_dir / self.experiments_file
        )

        experiments = {
            name: config
            for name, config in all_experiments.items()
            if name in run_config.get("Experiments", [])
        }

        if not experiments:
            raise ValueError("No experiments found or specified in the run file.")

        return experiments

    async def _run_single_experiment(
        self, name: str, settings: Dict[str, Any]
    ) -> float:
        """
        Run a single experiment and return its execution time.

        ### Args:
        - `name` (str): Name of the experiment
        - `settings` (Dict[str, Any]): Experiment settings

        ### Returns:
        - `float`: Execution time in seconds
        """
        start_time = time.time()

        # Prepare experiment configuration
        pre_build_injections = settings["pre_build_injections"]
        post_build_injections = settings["post_build_injections"]
        output_folder = settings["output_folder"] + "/" + name

        # Change the plot folder specifically for the experiment
        pre_build_injections.setdefault("General", {})["outputFolder"] = output_folder

        # Generate experiment config
        temp_config_file = self.temp_dir / f"{name}.yaml"
        config = ConfigurationBuilder(
            config_file_path=self.base_config,
            module_dir=self.module_dir,
            pre_build_injections=pre_build_injections,
            post_build_injections=post_build_injections,
        )
        config.save_to_yaml(temp_config_file)
        self.logger.debug(f"Generated configuration for {name} at {temp_config_file}")

        # Run experiment
        mapper = CSFMUMapper(
            config_path=temp_config_file,
            module_dir=self.module_dir,
            debug=self.debug,
        )
        await mapper.run()

        execution_time = time.time() - start_time
        return execution_time

    async def run(self, working_dir: Optional[Path] = None) -> Dict[str, float]:
        """
        Run all experiments specified in the run configuration.

        ### Args:
        - `working_dir` (Optional[Path]): Working directory for experiment execution.
                                        Defaults to None (uses current directory).

        ### Returns:
        - `Dict[str, float]`: Dictionary mapping experiment names to their execution times
        """
        if working_dir:
            original_dir = Path.cwd()
            os.chdir(working_dir)

        try:
            self._create_temp_directory()
            experiments = self._get_experiments()

            self.logger.info(f"Starting execution of {len(experiments)} experiments")
            experiment_times = {}

            for name, settings in experiments.items():
                self.logger.info(f"Running experiment: {name}")
                execution_time = await self._run_single_experiment(name, settings)
                experiment_times[name] = execution_time
                self.logger.info(f"Completed {name} in {execution_time:.2f} seconds")
                self.logger.info("-" * 80)

            total_time = sum(experiment_times.values())
            self.logger.info(
                f"All experiments completed. Total time: {total_time:.2f} seconds"
            )

            return experiment_times

        finally:
            if working_dir:
                os.chdir(original_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run experiments defined in YAML configuration files")
    parser.add_argument(
        "-bc",
        "--base_config",
        type=Path,
        default=Path(__file__).parent.parent / "example" / "configs" / "experiments" / "base_config.yaml",
        help="Path to the base configuration file",
    )
    parser.add_argument(
        "-md",
        "--module_dir", 
        type=Path,
        default=Path(__file__).parent.parent / "example" / "configs",
        help="Path to the directory containing module configurations",
    )
    parser.add_argument(
        "-ed",
        "--experiments_dir",
        type=Path,
        default=Path(__file__).parent.parent / "example" / "configs" / "experiments",
        help="Path to the directory containing experiment files",
    )
    parser.add_argument(
        "-ef",
        "--experiments_file",
        type=str,
        default="experiments.yaml",
        help="Name of the experiments definition file",
    )
    parser.add_argument(
        "-rf",
        "--run_file",
        type=str,
        default="run.yaml", 
        help="Name of the run configuration file",
    )
    parser.add_argument(
        "-td",
        "--temp_dir",
        type=str,
        default="temp",
        help="Name of temporary directory for generated configs",
    )
    parser.add_argument(
        "-wd",
        "--working_dir",
        type=Path,
        help="Working directory for experiment execution",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    runner = ExperimentRunner(
        base_config=args.base_config,
        module_dir=args.module_dir,
        experiments_dir=args.experiments_dir,
        experiments_file=args.experiments_file,
        run_file=args.run_file,
        temp_dir=args.temp_dir,
        debug=args.debug,
    )

    asyncio.run(runner.run(working_dir=args.working_dir))
