# CS-FMU-Mapper

## Installation

For usage only create a new python environment, install pyfmi manually via conda and this module via pip directly from git:

```bash
    > $ conda create -n cs-fmu-mapper python=3.10
    > $ conda activate cs-fmu-mapper
    > $ conda install -c conda-forge pyfmi
    > $ pip3 install git+https://github.com/marvin-schl/cs-fmu-mapper.git
```

Alternativley you can install after cloning the repo for development purposes:

```bash
    > $ conda create -n cs-fmu-mapper python=3.10
    > $ conda activate cs-fmu-mapper
    > $ conda install -c conda-forge pyfmi
    > $ pip3 install -r requirements.txt
```

This repository can be installed as a package via pip. The package has not yet been uploaded to PyPI. Therefore, the package has to be installed locally. By cloning the repository and executing the following command in the root directory of the repository the package will be installed. All dependencies will be installed automatically but note that pyfmi has to be installed manually as it cannot be installed via pip.

```bash
    > $ pip install -e .
```

## Executing Example

```bash
    > $ python -m cs_fmu_mapper.main -c example/config.yaml
```

## Configuration

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
...
# END_COMPONENT_DEFINITIONS
Algorithm:
  inputVar:
    {{ transform_vars(Model.outputVar, prefix='algo', direction='in') }}
  outputVar:
    {{ transform_vars(Model.inputVar, prefix='algo', direction='out') }}
```

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
...
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
...
```
## Usage

The example can be executed via the following command:

```bash
> $ python main.py -c example/configs/config.yaml
```
Or with a [modular config](example/configs/modular_config.yaml):

```bash
> $ python main.py -c example/configs/modular_config.yaml
```

## Implementing new Components

A custom simulation component can be created by inheriting from SimulationComponent. The inherited class should define a class variable `type` which value determines the value of the `type` field in the configuration file. Also, all abstract methods from SimulationComponent have to be implemented. Place the custom class inside the subpackage `components`. The constructor should take two arguments the corresponding section of the configuration as dict and a name. A minimal simulation component could look like:

```python
from simulation_component import SimulationComponent

class CustomComponent(SimulationComponent):
    type = "custom"

    def __init__(self, config, name):
        pass

    def do_step(self, t, dt):
        pass

```

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

## Known Issues

## TODOs

- [x] Make do_step() method async 
  - [ ] to be tested
- [x] Add a start_component() method to the SimulationComponent class that automatically does the async initialization of the component. This method should be called in the main loop of the program.
    => initialize method added in Simulation Component is called by mapper before first do_step() 
- [ ] Make sure that AbstractOPCUA client uses its own logger and not the SimulationComponent logger
- [ ] Add comments to methods
