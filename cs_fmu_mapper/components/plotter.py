import os
from abc import ABC, abstractmethod
from copy import copy

import matplotlib.pyplot as plt
import pandas as pd
from cs_fmu_mapper.components.simulation_component import SimulationComponent
from matplotlib.axes import Axes
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure


class Plotter(SimulationComponent):

    type = "plotter"

    def __init__(self, config, name):
        super(Plotter, self).__init__(config, name)
        self._t = []
        self._data = {}
        self._output_path = config["outputFolder"]
        self._plots_path = self._output_path + "/plots"
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
        self._log.info("Saving data to: " + self._output_path + "/data.csv")
        df.to_csv(self._output_path + "/data.csv", index=False)

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
            if not os.path.exists(self._plots_path):
                os.makedirs(self._plots_path)
            self.save_data()

            # Create PDF for merged plots if specified
            merge_pdf = None
            if "mergePlot" in self._config and self._config["mergePlot"]:
                merge_pdf = PdfPages(
                    os.path.join(self._output_path, "merged_plots.pdf")
                )

            for plot_name, plot_config in self._config["plots"].items():
                plot_config["path"] = self._plots_path
                plot_config["plot_name"] = plot_name
                plot_config["merge_pdf"] = merge_pdf
                if "type" in plot_config.keys():
                    plot = PlotFactory.instantiate_plot(
                        plot_config["type"], self._data, plot_config
                    )
                    plot.generate()
                    self._log.info(f"Plot '{plot_name}' generated.")
                else:
                    raise ValueError(f"Plot type not specified for plot {plot_name}")

            if merge_pdf is not None:
                merge_pdf.close()
                self._log.info(
                    f"Merged plots saved to {os.path.join(self._output_path, 'merged_plots.pdf')}"
                )

        self._log.info(f"Plots generated. View them at {self._output_path}")
        return True


def convert_units(data: dict, vars: list, unit_config: dict):
    """Convert units based on the provided configuration"""
    from_unit = unit_config.get("from", "")
    to_unit = unit_config.get("to", "")

    if from_unit == to_unit:
        return data

    conversion_factor = 1
    conversion_offset = 0

    # Time
    if from_unit == "s" and to_unit == "h":
        conversion_factor = 1 / 3600
    elif from_unit == "s" and to_unit == "d":
        conversion_factor = 1 / 86400
    elif from_unit == "s" and to_unit == "min":
        conversion_factor = 1 / 60
    # Temperature
    elif from_unit == "C" and to_unit == "K":
        conversion_offset = 273.15
    elif from_unit == "K" and to_unit == "C":
        conversion_offset = -273.15
    # Power
    elif from_unit == "W" and to_unit == "kW":
        conversion_factor = 1 / 1000
    elif from_unit == "W" and to_unit == "MW":
        conversion_factor = 1 / 1000000
    elif from_unit == "kW" and to_unit == "W":
        conversion_factor = 1000
    elif from_unit == "MW" and to_unit == "W":
        conversion_factor = 1000000
    # Percentage
    elif from_unit == "percent1" and to_unit == "percent100":
        conversion_factor = 100
    elif from_unit == "percent100" and to_unit == "percent1":
        conversion_factor = 1 / 100
    # Pressure
    elif from_unit == "Pa" and to_unit == "mWC":
        conversion_factor = 1 / 9806.65
    elif from_unit == "mWC" and to_unit == "Pa":
        conversion_factor = 9806.65
    elif from_unit == "Pa" and to_unit == "bar":
        conversion_factor = 1 / 100000
    elif from_unit == "bar" and to_unit == "Pa":
        conversion_factor = 100000
    elif from_unit == "mWC" and to_unit == "bar":
        conversion_factor = 0.0980665
    elif from_unit == "bar" and to_unit == "mWC":
        conversion_factor = 10.1972

    for var in vars:
        data[var] = [
            (value + conversion_offset) * conversion_factor for value in data[var]
        ]

    return data


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

        # Save to merged PDF if specified
        if "merge_pdf" in self._config and self._config["merge_pdf"] is not None:
            self._config["merge_pdf"].savefig(fig)

        # Save individual files
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
            self._data = convert_units(self._data, ["time"], self._config["xUnit"])
        if "yUnit" in self._config.keys():
            self._data = convert_units(
                self._data, self._config["vars"], self._config["yUnit"]
            )
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
                **self._config.get("plot_kwargs", {}),
            )
        if "limits" in self._config.keys():
            if "x" in self._config["limits"]:
                ax.set_xlim(
                    self._config["limits"]["x"][0], self._config["limits"]["x"][1]
                )
            if "y" in self._config["limits"]:
                ax.set_ylim(
                    self._config["limits"]["y"][0], self._config["limits"]["y"][1]
                )
        if "textfield" in self._config:
            prefix = self._config["textfield"].get("prefix", "")
            var = self._config["textfield"].get("var", "time")
            round_digits = self._config["textfield"].get("round", 2)
            suffix = self._config["textfield"].get("suffix", "")

            if "unit" in self._config["textfield"]:
                self._data = convert_units(
                    self._data, [var], self._config["textfield"]["unit"]
                )

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
            self._data = convert_units(self._data, [x_var], self._config["xUnit"])
        if "yUnit" in self._config.keys():
            self._data = convert_units(
                self._data, self._config["vars"], self._config["yUnit"]
            )

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
                **self._config.get("plot_kwargs", {}),
            )

        if "limits" in self._config.keys():
            if "x" in self._config["limits"]:
                ax.set_xlim(
                    self._config["limits"]["x"][0], self._config["limits"]["x"][1]
                )
            if "y" in self._config["limits"]:
                ax.set_ylim(
                    self._config["limits"]["y"][0], self._config["limits"]["y"][1]
                )

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
