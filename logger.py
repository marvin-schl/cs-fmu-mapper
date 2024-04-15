from interfaces import IMappable
import pandas as pd
import matplotlib.pyplot as plt
import logging

class Logger(IMappable):
    def __init__(self, config, name):        
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.info("Initializing Logger.")
        self._config = config
        self._name = name 
        self._input_values ={k : self._config["inputVar"][k]["init"] for k in self._config["inputVar"].keys()}
        self._t = []
        self._data = {}
        for key in self._config["inputVar"].keys():
            self._data[self._config["inputVar"][key]["nodeID"]] = []
        
    def set_input_values(self, new_val):
        self._input_values = new_val

    def set_input_value(self, name, new_val):
        self._input_values[name] = new_val

    def contains(self, name):
        return (name in self._input_values.keys()) 

    def get_node_by_name(self, name):
        if name in self._config["inputVar"].keys():
            return self._config["inputVar"][name]["nodeID"]
        else:
            return None

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
        self._log.info("Saving data to: " + self._config["path"]+"\\data.csv")
        df.to_csv(self._config["path"]+"\\data.csv", sep=";", index=False)
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

    def get_name(self):
        return self._name
    
    def get_type(self):
        return self._config["type"]