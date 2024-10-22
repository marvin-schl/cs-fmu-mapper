import os
from abc import ABC, abstractmethod
from copy import copy

import matplotlib.pyplot as plt
import pandas as pd
from cs_fmu_mapper.components.simulation_component import SimulationComponent
from matplotlib.axes import Axes
from matplotlib.figure import Figure


class Plotter(SimulationComponent):

    type = "plotter"

    def __init__(self, config, name):
        super(Plotter, self).__init__(config, name)
        self._t = []
        self._data = {}
        self._path = config["outputFolder"]
        self._exclude_n_values = (
            3
            if "exclude_n_values" not in self._config
            else self._config["exclude_n_values"]
        )
        for key in self._config["inputVar"].keys():
            self._data[self._config["inputVar"][key]["nodeID"]] = []

    def get_output_values(self):
        raise NotImplementedError()

    async def do_step(self, t, dt):
        for key, val in self.get_input_values().items():  # type: ignore
            nodeID = self.get_node_by_name(key)
            self._data[nodeID].append(val)
        self._t.append(t)
        return True

    def save_data(self):
        df = pd.DataFrame(self._data)
        self._log.info("Saving data to: " + self._path + "/data.csv")
        df.to_csv(self._path + "/data.csv", index=False)

    async def finalize(self):
        self._log.info("Generating Plots.")
        self._data["time"] = self._t

        if "usetex" in self._config.keys():
            plt.rcParams.update(
                {
                    "text.usetex": self._config["usetex"],
                }
            )

        if "fontfamily" in self._config.keys():
            plt.rcParams.update(
                {
                    "font.family": self._config["fontfamily"],
                }
            )
        # Remove the first n values from the data
        for column in self._data.keys():
            self._data[column] = self._data[column][self._exclude_n_values :]
        # Generate plots
        if "plots" in self._config.keys():
            if not os.path.exists(self._path):
                os.makedirs(self._path)
            self.save_data()
            for plot_name, plot_config in self._config["plots"].items():
                plot_config["path"] = self._path
                if "type" in plot_config.keys():
                    plot = PlotFactory.instantiate_plot(
                        plot_config["type"], self._data, plot_config
                    )
                    plot.generate()
                    self._log.info(f"Plot '{plot_name}' generated.")
                else:
                    raise ValueError(f"Plot type not specified for plot {plot_name}")
        self._log.info(f"Plots generated. View them at {self._path}")
        return True


class BasePlot(ABC):
    """Base class for all plots"""

    def __init__(self, data, config):
        self._data = copy(data)
        self._title = config["title"]
        self._config = config
        self._final_time = self._data["time"][-1]

    @abstractmethod
    def generate(self):
        pass

    def convert_units(self, vars: list, unit_config: dict):
        """Convert units based on the provided configuration"""
        from_unit = unit_config.get("from", "")
        to_unit = unit_config.get("to", "")

        if from_unit == to_unit:
            return

        conversion_factor = 1
        conversion_offset = 0

        if from_unit == "s" and to_unit == "h":
            conversion_factor = 1 / 3600
        elif from_unit == "s" and to_unit == "d":
            conversion_factor = 1 / 86400
        elif from_unit == "C" and to_unit == "K":
            conversion_offset = 273.15
        elif from_unit == "K" and to_unit == "C":
            conversion_offset = -273.15
        elif from_unit == "W" and to_unit == "kW":
            conversion_factor = 1 / 1000
        elif from_unit == "W" and to_unit == "MW":
            conversion_factor = 1 / 1000000
        elif from_unit == "kW" and to_unit == "W":
            conversion_factor = 1000
        elif from_unit == "MW" and to_unit == "W":
            conversion_factor = 1000000

        for var in vars:
            self._data[var] = [
                (value + conversion_offset) * conversion_factor
                for value in self._data[var]
            ]

    def finalize(self, fig: Figure, ax: Axes, filetypes: list = ["pdf"]):
        """Finalize the plot and save it to the specified path"""
        if "legend" in self._config.keys():
            ax.legend()
        ax.set(
            xlabel=self._config["xlabel"],
            ylabel=self._config["ylabel"],
            title=self._config["title"],
        )
        if "grid" in self._config and self._config["grid"]:
            ax.grid(True, which="major", linewidth="0.5", color="black", alpha=0.4)
        if "subgrid" in self._config and self._config["subgrid"]:
            ax.minorticks_on()
            ax.grid(
                which="minor", linestyle=":", linewidth="0.5", color="black", alpha=0.25
            )
        for filetype in filetypes:
            fig.savefig(
                self._config["path"]
                + "/"
                + self._title.replace(" ", "_")
                + "."
                + filetype
            )
        plt.close(fig)


class TimeSeriesPlot(BasePlot):
    """Time series plot"""

    def __init__(self, data, config):
        super().__init__(data, config)

    def generate(self):
        fig, ax = plt.subplots(figsize=(20, 5))
        if "xUnit" in self._config.keys():
            self.convert_units(["time"], self._config["xUnit"])
        if "yUnit" in self._config.keys():
            self.convert_units(self._config["vars"], self._config["yUnit"])
        for i, var in enumerate(self._config["vars"]):
            ax.plot(
                self._data["time"],
                self._data[var],
                label=(
                    self._config["legend"][i]
                    if "legend" in self._config.keys()
                    else None
                ),
                linewidth=(
                    0.5
                    if "linewidth" not in self._config.keys()
                    else self._config["linewidth"]
                ),
            )
        if "limits" in self._config.keys():
            if "x" in self._config["limits"]:
                ax.set_xlim(self._config["limits"]["x"])
            if "y" in self._config["limits"]:
                ax.set_ylim(self._config["limits"]["y"])
        if "textfield" in self._config:
            prefix = self._config["textfield"].get("prefix", "")
            var = self._config["textfield"].get("var", "time")
            round_digits = self._config["textfield"].get("round", 2)
            suffix = self._config["textfield"].get("suffix", "")

            if "unit" in self._config["textfield"]:
                self.convert_units([var], self._config["textfield"]["unit"])

            value = self._data[var][-1] if var in self._data else ""

            text = f"{prefix}{value:.{round_digits}f}{suffix}"
            x = self._config["textfield"].get("x", 0.05)
            y = self._config["textfield"].get("y", 0.95)
            fontsize = self._config["textfield"].get("fontsize", 10)
            ax.text(
                x,
                y,
                text,
                transform=ax.transAxes,
                fontsize=fontsize,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
            )
        self.finalize(fig, ax)


class ScatterPlot(BasePlot):
    """Scatter plot"""

    def __init__(self, data, config):
        super().__init__(data, config)

    def generate(self):
        fig, ax = plt.subplots()
        x_var = self._config["x_var"]
        x_values = self._data[x_var]

        if "xUnit" in self._config.keys():
            self.convert_units([x_var], self._config["xUnit"])
        if "yUnit" in self._config.keys():
            self.convert_units(self._config["vars"], self._config["yUnit"])

        for i, var in enumerate(self._config["vars"]):
            ax.plot(
                x_values,
                self._data[var],
                "x",
                label=(
                    self._config["legend"][i]
                    if "legend" in self._config.keys()
                    else None
                ),
            )

        if "limits" in self._config.keys():
            if "x" in self._config["limits"]:
                ax.set_xlim(self._config["limits"]["x"])
            if "y" in self._config["limits"]:
                ax.set_ylim(self._config["limits"]["y"])

        self.finalize(fig, ax)


class PlotFactory:
    """Factory class for creating plots"""

    plot_types = {"time_series": TimeSeriesPlot, "scatter": ScatterPlot}

    @staticmethod
    def instantiate_plot(plot_type, data, config):
        if plot_type in PlotFactory.plot_types:
            return PlotFactory.plot_types[plot_type](data, config)
        else:
            raise NotImplementedError(f"Plot type {plot_type} not implemented")
