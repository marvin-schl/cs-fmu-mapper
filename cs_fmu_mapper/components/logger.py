import pandas as pd
import matplotlib.pyplot as plt
import logging
from cs_fmu_mapper.components.simulation_component import SimulationComponent


class Logger(SimulationComponent):

    type = "logger"

    def __init__(self, config, name):
        super(Logger, self).__init__(config, name)
        self._t = []
        self._data = {}
        for key in self._config["inputVar"].keys():
            self._data[self._config["inputVar"][key]["nodeID"]] = []
        self._usetex = False
        if "usetex" in self._config.keys():
            self._usetex = self._config["usetex"]

    def get_output_values(self):
        raise NotImplementedError()

    async def do_step(self, t, dt):
        for key, val in self.get_input_values().items():
            nodeID = self.get_node_by_name(key)
            self._data[nodeID].append(val)
        self._t.append(t)
        return True

    async def finalize(self):
        self._log.info("Finalizing Logger.")
        self._data["time"] = self._t

        plt.rcParams.update(
            {
                "text.usetex": self._usetex,
            }
        )

        if "fontfamily" in self._config.keys():
            plt.rcParams.update(
                {
                    "font.family": self._config["fontfamily"],
                }
            )

        if "plots" in self._config.keys():
            for plot in self._config["plots"].keys():
                if "type" in self._config["plots"][plot].keys():
                    match self._config["plots"][plot]["type"]:
                        case "time_series":
                            self.generate_time_series_plot(plot)
                        case "scatter":
                            self.generate_scatter_plot(plot)
                        case _:
                            raise NotImplementedError(
                                "Plot type "
                                + self._config["plots"][plot]["type"]
                                + "not implemented."
                            )
                else:
                    self.generate_time_series_plot(plot)

        df = pd.DataFrame(self._data)
        self._log.info("Saving data to: " + self._config["path"] + "\data.csv")
        df.to_csv(self._config["path"] + "\data.csv", sep=";", index=False)
        self._log.info("Logger finalized.")
        return True

    def generate_time_series_plot(self, name):
        self._log.info(
            "Generating time series plot " + name + " to: " + self._config["path"]
        )
        plot_config = self._config["plots"][name]

        fig, ax = plt.subplots()
        for var in plot_config["vars"]:
            nodeID = self.get_node_by_name(var)
            ax.plot(self._t, self._data[nodeID])
        if "legend" in plot_config.keys():
            ax.legend(plot_config["legend"])
        ax.set(
            xlabel=plot_config["xlabel"],
            ylabel=plot_config["ylabel"],
            title=plot_config["title"],
        )
        if "grid" in plot_config and plot_config["grid"]:
            ax.grid(True, which="major", linewidth="0.5", color="black", alpha=0.9)
        if "subgrid" in plot_config and plot_config["subgrid"]:
            ax.minorticks_on()
            ax.grid(
                which="minor", linestyle=":", linewidth="0.5", color="black", alpha=0.75
            )
        if self._usetex:
            fig.savefig(self._config["path"] + "\\" + name + ".pgf")
        fig.savefig(self._config["path"] + "\\" + name + ".png")
        plt.close(fig)

    def generate_scatter_plot(self, name):
        self._log.info(
            "Generating time scatter plot " + name + " to: " + self._config["path"]
        )
        plot_config = self._config["plots"][name]
        x_value = self._data[self.get_node_by_name(plot_config["x_var"])]
        fig, ax = plt.subplots()
        for var in plot_config["vars"]:
            nodeID = self.get_node_by_name(var)
            ax.plot(x_value, self._data[nodeID], "x")
        if "legend" in plot_config.keys():
            ax.legend(plot_config["legend"])
        ax.set(
            xlabel=plot_config["xlabel"],
            ylabel=plot_config["ylabel"],
            title=plot_config["title"],
        )
        if "grid" in plot_config and plot_config["grid"]:
            ax.grid(True, which="major", linewidth="0.5", color="black", alpha=0.9)
        if "subgrid" in plot_config and plot_config["subgrid"]:
            ax.minorticks_on()
            ax.grid(
                which="minor", linestyle=":", linewidth="0.5", color="black", alpha=0.75
            )
        if self._usetex:
            fig.savefig(self._config["path"] + "\\" + name + ".pgf")
        fig.savefig(self._config["path"] + "\\" + name + ".png")
        plt.close(fig)
