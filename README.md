# CS-FMU-Mapper

The CS-FMU-Mapper is a Python-based co-simulation framework that enables seamless integration and mapping between FMUs or OPCUA nodes and other simulation components. It provides a flexible configuration system to define component interactions, data mappings, and simulation scenarios.

- [CS-FMU-Mapper](#cs-fmu-mapper)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Usage](#usage)
    - [Command Line Usage](#command-line-usage)
    - [Python Module Usage](#python-module-usage)
  - [Configuration](#configuration)
    - [Basic Configuration](#basic-configuration)
    - [ConfigurationBuilder](#configurationbuilder)
      - [Modular Configs](#modular-configs)
      - [List Merge Mode](#list-merge-mode)
  - [Mappings](#mappings)
  - [Scenarios](#scenarios)
  - [Plotter](#plotter)
  - [Implementing Custom Components](#implementing-custom-components)
    - [Creating a Custom Component](#creating-a-custom-component)
    - [Integrating a Custom Component](#integrating-a-custom-component)
    - [Accessing Component Inputs and Outputs](#accessing-component-inputs-and-outputs)
  - [Advanced Features](#advanced-features)
    - [Experiment Runner](#experiment-runner)
    - [Scheduler](#scheduler)
  - [Known Issues](#known-issues)
  - [Contributing](#contributing)

## Installation

Create a new Python environment, e.g. with conda, and install the required dependencies:

```bash
    > $ conda create -n cs-fmu-mapper python=3.10
    > $ conda activate cs-fmu-mapper
    > $ pip3 install git+https://github.com/marvin-schl/cs-fmu-mapper.git
```

Alternativley you can install after cloning the repo for development purposes:

```bash
    > $ conda create -n cs-fmu-mapper python=3.10
    > $ conda activate cs-fmu-mapper
    > $ pip3 install -r requirements.txt
```

This repository can be installed as a package via pip. The package has not yet been uploaded to PyPI. Therefore, the package has to be installed locally. By cloning the repository and executing the following command in the root directory of the repository the package will be installed. All dependencies will be installed automatically but note that pyfmi has to be installed manually as it cannot be installed via pip.

```bash
    > $ pip install -e .
```

## Quick Start

```bash
    > $ python -m cs_fmu_mapper.main -c example/configs/config.yaml
```

This will run the simulation with the configuration given in [example/config.yaml](example/config.yaml) and will save the results in the [example/results](example/results) directory.

## Usage

The cs-fmu-mapper can be run directly from the command line or imported as a module in your own Python code.

### Command Line Usage

```bash
    > $ python -m cs_fmu_mapper.main -c example/configs/config.yaml -md example/configs/scenario --debug
```

The arguments are the following:

- `-c` or `--config_path`: Path to the configuration file.
- `-md` or `--module_dir`: Path to the directory containing the modular config files (only needed if modular config is used).
- `-d` or `--debug`: Run in debug mode.

### Python Module Usage

For simplicity, create a own python file and import the `CSFMUMapper` class from the `cs_fmu_mapper` module and call the `run()` method with the desired arguments.

```python
import asyncio
from cs_fmu_mapper.main import CSFMUMapper

mapper = CSFMUMapper(config_path, module_dir, debug)
asyncio.run(mapper.run())
```

## Configuration

### Basic Configuration

Configuration is done in YAML format. The configuration file can also be formatted as JSON but YAML is recommended as it supports commenting. A detailed commented example configuration is given [here](example/config.yaml).

The configuration basically defines simulation components of type `plc`, `fmu`, `logger` and/or `scenario`. Each components' section defines `ouputVar`s and/or `inputVar`s by specifying their component-specific access string called `nodeID`, e.g. the OPCUA NodeID for a `plc` component or the CSV column name of a `scenario` component. Configuration of `scenario` and `logger` components are optional. Configuration of `plc` component is also optional but only makes sense if there is at least a `scenario` or another custom component configured which interacts with the `fmu`.

Besides the component configuration, there is a `Mapping` section where the Mapping from `outputVar`s to `inputVar`s is configured. For a detailed explanation see the example config. The simulation will be performed in steps. If a mapping is configured as `preStepMapping` the mapping will be done before simulation step execution. Consequently, when a mapping is configured as `postStepMapping` the mapping will be done afterwards.

If there is a `plc` component configured the `plc` will be the simulation master and will trigger each simulation step. If there is no `plc` configured the software will simulate standalone with the configured step size `timeStepPerCycle` configured in the `Mapping` section. If every component signalizes that it is finished then every component will be notified that the simulation is finished. In standalone mode, the simulation will then finalize itself. In `plc` master mode the `plc` should react accordingly and should initiate the termination of the program.

### ConfigurationBuilder

The `ConfigurationBuilder` class takes the following arguments:

- `config_file_path`: Absolute or relative path to the configuration file.
- `module_dir`: Absolute or relative path to the modular config files.
- `pre_build_injections`: (optional) Additional dictionary to inject before the build process.
- `post_build_injections`: (optional) Additional dictionary to inject after the build process.

#### Modular Configs

Modular configurations allow for a more flexible and scalable configuration of simulations. Instead of defining all components in a single file, you can split the configuration into multiple files and directories. This approach enhances reusability and maintainability of the configuration.

An Example for a modular configuration is given [here](example/configs/modular_config.yaml). Modular configurations are enabled by setting the `modular_config` flag to `true`. Otherwise the configuration is treated as a full config.

The modular config is technically split into two parts by the `# END_COMPONENT_DEFINITIONS` tag:

1. The 'settings' config which contains all the components that are used to build the full config. Must contain a `Components` key.
2. Optional overrides for the components defined in the settings config.

The modular configs that are imported from the `Components` section can also be [jinja2 templates](https://jinja.palletsprojects.com/en/2.10.x/templates/). This allows for a high degree of flexibility as the components can be parametrized. For example the `inputVar` and `outputVar` can be transformed from other component's `outputVar` and `inputVar` respectively. For example:

```yaml
# modular_config.yaml
---
# END_COMPONENT_DEFINITIONS
Algorithm:
  inputVar:
    { { transform_vars(Model.outputVar, prefix='algo', direction='in') } }
  outputVar:
    { { transform_vars(Model.inputVar, prefix='algo', direction='out') } }
```

The `transform_vars` function is a function that is used to transform the variables (see [ConfigurationBuilder](cs_fmu_mapper/config.py)).

```yaml
# model.yaml
Model:
  inputVar:
    model.in.u:
      nodeID: u
  outputVar:
    model.out.y:
      nodeID: y
```

The full config will then look like this:

```yaml
# full_config.yaml
---
Model:
  inputVar:
    model.in.u:
      nodeID: u
  outputVar:
    model.out.y:
      nodeID: y

Algorithm:
  inputVar:
    algo.in.y:
      nodeID: y
  outputVar:
    algo.out.u:
      nodeID: u
```

#### List Merge Mode

The `ListMergeMode` is an enum that determines how lists should be merged. The default is `EXTEND_UNIQUE` which extends the list by adding unique elements and is the most useful mode. The other modes are `EXTEND` which extends the list by adding all elements and `REPLACE` which replaces the list with the new list. For more information see the [OmegaConf documentation](https://omegaconf.readthedocs.io/en/latest/usage.html#omegaconf-merge).

In order to change the `ListMergeMode` for a specific injection just add the `list_merge_mode` key to the injection dictionary. For example:

```yaml
injection:
  list_merge_mode: EXTEND # or EXTEND_UNIQUE or REPLACE. Defaults to EXTEND_UNIQUE (if not specified)
  ...
```

## Mappings

Mappings are used to map the output variables of one component to the input variables of another component. The mapping is configured in the `Mapping` section of the configuration file. For an example see [example/configs/config.yaml](example/configs/config.yaml) and the [OPCUAFMUMapper](cs_fmu_mapper/components/opcua_fmu_mapper.py) class.

The mapping is done in two steps:

1. The `preStepMappings` are applied before every simulation step.
2. The `postStepMappings` are applied after every simulation step.

The mappings are configured as a dictionary where the keys are the names of the source components and the values are lists of the input variables of the destination component that shall be mapped to the output variables of the source component. For example:

```yaml
Mapping:
  preStepMappings:
    algo.out.TIR:
      - model.in.TIR
  postStepMappings:
    model.out.TIR:
      - algo.in.TIR
```

The above configuration will map the `TIR` output variable of the `algo` component to the `TIR` input variable of the `model` component before every simulation step and the `TIR` output variable of the `model` component to the `TIR` input variable of the `algo` component after every simulation step.

It is also possible to map multiple input variables to the same output variable. This can be useful if the same input variable is needed in different components (e.g. for plotting). In this case, just add multiple entries to the list like this:

```yaml
Mapping:
  preStepMappings:
    algo.out.TIR:
      - model.in.TIR
      - plot.in.TIR
```

## Scenarios

Scenarios are instructions for the simulation or other components to follow. The scenario is configured in the `Scenario` section of the configuration file. For an example see [example/configs/config.yaml](example/configs/config.yaml) and the [Scenario](cs_fmu_mapper/components/scenario.py) class. The scenario component is optional.

It takes two types of inputs:

- **Python file**: this must contain a class which inherits from the [ScenarioBase](cs_fmu_mapper/components/scenario.py) class and implements the `generate_schedule` method. This method takes some kwargs defined in the `parameters` section of the scenario configuration and returns a [pandas dataframe](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html) with at least a `t` column containing the simulation time and the new values for the scenario inputs. The columns of the dataframe must be named after the scenarios output variables. The parameters section must contain the path to the python file as key and the kwargs as values.
- **CSV file**: this must be loadable as a [pandas dataframe](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html) with the `t` column containing the simulation time and the columns containing the new values for the scenario outputs.

If the [mappings](##mappings) are configured correctly the scenarios outputs will be mapped to the other components inputs.

> [!NOTE]
> If multiple scenarios are defined the `scenario` component will automatically concatenate and overwrite them. The order of the scenarios in the configuration file defines the order in which they are concatenated / overwritten.

## Plotter

The plotter is a component that can be used to plot the output variables of the simulation. It is configured in the `Plotter` section of the configuration file. For an example see [example/configs/config.yaml](example/configs/config.yaml) and the [Plotter](cs_fmu_mapper/components/plotter.py) class.

## Implementing Custom Components

### Creating a Custom Component

A custom simulation component can be created by inheriting from [SimulationComponent](cs_fmu_mapper/components/simulation_component.py). The inherited class should define a class variable `type` which value determines the value of the `type` field in the configuration file. Also, all abstract methods from SimulationComponent have to be implemented. The constructor should take two arguments the corresponding section of the configuration as dict and a name. A minimal simulation component could look like:

```python
from simulation_component import SimulationComponent

class CustomComponent(SimulationComponent):
    type = "custom"

    def __init__(self, config, name):
        pass

    def do_step(self, t, dt):
        pass
```

To get an overview of the methods that need to be implemented, see the [SimulationComponent](cs_fmu_mapper/components/simulation_component.py) class.

### Integrating a Custom Component

To integrate the custom component into the simulation, it has to be added to the configuration file. The component will then automatically be initialized and the `do_step()` method will be executed in every simulation step. To add a custom component to the configuration file, add it under the `customComponents` section in the `General` key. For example:

```yaml
General:
  customComponents:
    CustomComponentClass:
      pathToComponent: path.to.custom.component
```

The key `CustomComponentClass` is the class name of the custom component and the `pathToComponent` is the path to the custom component class.

### Accessing Component Inputs and Outputs

SimulationComponent buffers the mapped input and output values in two dictionaries. One for input and the other for output values. There are getters and setters for getting and setting single values or the whole dict. The two dicts shall only be accessed by those getters and setters:

```python
    # for setting/getting the while input dict
    def get_input_values(self)
    def set_input_values(self, new_val)
    # for setting/getting single values in the input dict
    def get_input_value(self, name)
    def set_input_value(self, name, new_val)
    # for setting/getting the whole output dict
    def get_output_values(self)
    def set_output_values(self, new_val)
    # for setting/getting single values in the output dict
    def get_output_value(self, name)
    def set_output_value(self, name, new_val)

```

The implementation of `doStep()` should read the component's output values and write them into the SimulationComponents output buffer via the above-mentioned methods. Accordingly, it should read the input buffer and write them to the component inputs. The `name` arguments of the above methods represent the configured unique keys of the `outputVar`/`inputVar` section of the component. If no `outputVar` or `inputVar` are configured the according getters and setters raise a `NotImplementedError`.

Optionally the component can implement the following methods:

```python
    def is_finished(self)
    def notify_simulation_finished(self)
    def finalize(self)
```

If the component shall affect the end of a simulation its `is_finished()` method should return `false` as long as it isn't finished. The default return value if not implemented is `true`. As soon as every component finishes its execution the `notify_simulation_finshed()` callback is called. The `finalize()` callback is called shortly before the termination of the program. Any open connections could be closed here, or occupied memory could be freed here for example.

For logging purposes, these three methods can be used:

```python
    def log_info(self, msg)
    def log_debug(self, msg)
    def log_warning(self, msg)
```

## Advanced Features

### Experiment Runner

The experiment runner allows for running multiple preconfigured simulations in a row. This can be useful to compare the results of different simulations without having to manually change the configuration and run the simulation multiple times.

This is done with the [ExperimentRunner](cs_fmu_mapper/experiment_runner.py) class.
For an example, execute the following command:

```bash
    > $ python -m cs_fmu_mapper.experiment_runner
```

This will run all the experiments specified in the [run.yaml](example/configs/experiments/run.yaml) file, that where defined in the [experiments.yaml](example/configs/experiments/experiments.yaml) file and save the results in the [example/results](example/results) directory. The [base_config.yaml](example/configs/experiments/base_config.yaml) is used as the base configuration for all the experiments which will be extended by the parameters defined in the [experiments.yaml](example/configs/experiments/experiments.yaml) file. There, the `output_folder` is the directory where the results will be saved. Each experiment will create a subdirectory in the `output_folder` with the name of the experiment. The `pre_build_injections` and `post_build_injections` sections of the experiment configuration will be used to overwrite the corresponding sections of the base configuration. See the [ConfigurationBuilder](cs_fmu_mapper/configuration_builder.py) class for more information about the injections.

The experiment runner takes the following arguments:

- `-bc` or `--base_config`: Path to the base configuration file (which gets extended by the experiments).
- `-md` or `--module_dir`: Path to the directory containing the module configurations (for the modular config).
- `-ed` or `--experiments_dir`: Path to the directory containing the experiment configurations (directory containing the [experiments.yaml](example/configs/experiments/experiments.yaml) and [run.yaml](example/configs/experiments/run.yaml) files).
- `-ef` or `--experiments_file`: Name of the experiments definition file. Defaults to `experiments.yaml`.
- `-rf` or `--run_file`: Name of the run definition file. Defaults to `run.yaml`.
- `-td` or `--temp_dir`: Name of the temporary directory for generated configs. Defaults to `temp`.
- `-wd` or `--working_dir`: Working directory for experiment execution.
- `-d` or `--debug`: Run in debug mode.

### Scheduler

The scheduler allows for customizable scenarios based on time-value patterns. This is done by defining a scenario path that begins with `Scheduler` in the `Scenario` component configuration and defining the parameters in the `parameters` section. For an example see [customScenario.yaml](example/configs/scenario/customScenario.yaml). In the `scenario` component configuration the `parameters` are used to define the parameters of the `Scheduler` class.

The scheduler takes the following arguments:

- `duration`: Duration of the schedule in seconds. It is used to determine the length of the schedule. The patterns are repeated over the duration. Defaults to 4 days.
- `items`: List of items to be scheduled. It is used to define the column names of the schedule (the `column_prefix` parameter of the Scheduler class is automatically prepended to each item to allow for custom column names). Defaults to `DEFAULT_ITEMS`.
- `times`: List of times at which the schedule changes. It is a list of integers and is used to define the times at which the schedule changes. If not specified the times are automatically determined by the length of the patterns and will be evenly spaced over the interval of the time unit (hours: over 24 hours, minutes: over 60 minutes, seconds: over 60 seconds). Defaults to `None`.
- `patterns`: Dictionary containing the time-value patterns. It is used to define the time-value patterns and must be of the same length as the `times` parameter as each pattern is applied at the corresponding time. Defaults to `DEFAULT_PATTERNS`.
- `time_unit`: Unit of the `times` parameter. Can be either `"days"`, `"hours"`, `"minutes"` or `"seconds"`. Defaults to `"hours"`.
- `column_prefix`: Prefix for the column names of the schedule. Defaults to `"scen.out."`.
- `start_time`: Start time of the schedule. Defaults to `0`.

For example the following configuration:

```yaml
Scenario:
  path:
    - Scheduler: CustomScenario
  parameters:
    CustomScenario:
      duration: 7200
      items: ["u"]
      times: [0, 30, 59]
      patterns: { "1": [1, 0, 1] }
      time_unit: minutes
      column_prefix: "custom_"
      start_time: 3600
```

This will create a schedule where the value of `u` changes at times 1:00, 1:30 and 1:59, following the pattern [1, 0, 1]. This pattern starts at 3600 seconds (1:00) and repeats over the duration of 2 hours (7200 seconds).

In this example, notice that the pattern uses `"1"` as its key instead of `"u"`. When pattern keys don't match the item names in the `items` list, the scheduler will map them in order. So here, the pattern `"1": [1, 0, 1]` gets mapped to the item `"u"`.

This mapping behavior is particularly useful when running multiple simulations that use the same patterns but with different item names. You can keep the patterns constant in your scenario file and only update the `items` list to change which items receive those patterns.

## Known Issues

- The modular configs (jinja2 templates) have difficulties with code formatters like prettier. This can be fixed by adding the `# prettier-ignore` comment to the lines that should not be formatted.

## Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue on GitHub. If you want to contribute code, please fork the repository and create a pull request.
