
import pandas as pd
import matplotlib.pyplot as plt
import logging
from interfaces import SimulationComponent
class Logger(SimulationComponent):
    def __init__(self, config, name):        
        super(Logger, self).__init__(config, name)
        self._t = []
        self._data = {}
        for key in self._config["inputVar"].keys():
            self._data[self._config["inputVar"][key]["nodeID"]] = []

    def get_output_values(self):
        raise NotImplementedError()

    def do_step(self, t, dt):
        for key, val in self._input_values.items():
            nodeID = self.get_node_by_name(key)
            self._data[nodeID].append(val)
        self._t.append(t)
        return True

    def finalize(self):
        self._log.info("Finalizing Logger.")
        self._data["time"] = self._t
        if "plots" in self._config.keys():
            for plot in self._config["plots"].keys():
                self.generate_plot(plot)
        df = pd.DataFrame(self._data)
        self._log.info("Saving data to: " + self._config["path"]+"data.csv")
        df.to_csv(self._config["path"]+"data.csv", sep=";", index=False)
        self._log.info("Logger finalized.")
        return True
    
    def generate_plot(self, name):
        self._log.info("Generating plot: " + name + "to: " + self._config["path"])
        plot_config = self._config["plots"][name]

        fig, ax = plt.subplots()
        for var in plot_config["vars"]:
            nodeID = self.get_node_by_name(var)
            ax.plot(self._t, self._data[nodeID])
        ax.legend(plot_config["legend"])
        ax.set(xlabel=plot_config["xlabel"], ylabel=plot_config["ylabel"], title=plot_config["title"])
        if plot_config["grid"]:
            ax.grid(True, which="major", linewidth="0.5", color="black", alpha=0.9)
        if plot_config["subgrid"]:
            ax.minorticks_on()
            ax.grid(which="minor", linestyle=":", linewidth="0.5", color="black", alpha=0.75)
        fig.savefig(self._config["path"]+"\\"+name+".pgf")
        fig.savefig(self._config["path"]+"\\"+name+".png")
        plt.close(fig)

