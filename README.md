# CS-FMU-Mapper
A mapping and plotting tool for Co-simulation with FMU binary modells and PLCs using an OPC UA interface.
## Installation

```bash
    > $ conda create -n cs-fmu-mapper python=3.10
    > $ conda activate cs-fmu-mapper
    > $ conda install -c conda-forge pyfmi
    > $ pip3 install -r requirements.txt
```
<details>
    <summary>Click to explain!</summary>
    
    - creates a new conda environment named cs-fmu-mapper with Python version 3.10; both -n, --name will be accepted
    - activates the cs-fmu-mapper conda environment, making it the current working environment
    - installs the pyfmi package from the conda-forge channel into the currently active conda environment
    - uses pip to install the Python packages listed in the requirements.txt file into the currently active conda environment

read the documentation of [PyFMI](https://jmodelica.org/pyfmi/).
</details>

## Executing Example

```bash
    > $ python main.py -c example/config.yaml
```

## Configuration

Configuration is done in YAML format. The configuration file can also be formatted as JSON but YAML is recommended as it supports commenting. A detailed commented example configuration is given [here](example/config.yaml).

The configuration basically defines simulation components of type `plc`, `fmu`, `logger` and/or `scenario`. Each components' section defines `ouputVar`s and/or `inputVar`s by specifying their component-specific access string called `nodeID`, e.g. the OPCUA NodeID for a `plc` component or the CSV column name of a `scenario` component. Configuration of `scenario` and `logger` components are optional. Configuration of `plc` component is also optional but only makes sense if there is at least a `scenario` or another custom component configured which interacts with the `fmu`.

Besides the component configuration, there is a `Mapping` section where the Mapping from `outputVar`s to `inputVar`s is configured. For a detailed explanation see the example config. The simulation will be performed in steps. If a mapping is configured as `preStepMapping` the mapping will be done before simulation step execution. Consequently, when a mapping is configured as `postStepMapping` the mapping will be done afterwards.

If there is a `plc` component configured, the `plc` will be the simulation master and will trigger each simulation step. If there is no `plc` configured the software will simulate standalone with the configured step size `timeStepPerCycle` configured in the `Mapping` section. If every component signalizes that it is finished then every component will be notified that the simulation is finished. In standalone mode, the simulation will then finalize itself. In `plc` master mode the `plc` should react accordingly and should initiate the termination of the program.

## Usage

The example can be executed via the following command:

```bash
> $ python main.py -c example/config.yaml
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
## Class Diagram

![Class Diagram](img/class_diagram_cs_mapper.jpg)


## Known Issues

## TODOs

- [ ] Make do_step() method async
- [ ] Add a start_component() method to the SimulationComponent class that automatically does the async initialization of the component. This method should be called in the main loop of the program.
- [ ] Make sure that AbstractOPCUA client uses its own logger and not the SimulationComponent logger
