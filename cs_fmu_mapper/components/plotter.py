import os
from abc import ABC, abstractmethod
from copy import copy

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo
import plotly.colors
import webbrowser
from cs_fmu_mapper.components.simulation_component import SimulationComponent
from matplotlib.axes import Axes
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure


def clean_axis_label(label):
    """Clean axis labels to use proper Unicode symbols instead of LaTeX formatting"""
    if not label:
        return label

    # Replace common LaTeX degree symbols with Unicode
    label = label.replace("$^\\circ$", "°")
    label = label.replace("$^{\\circ}$", "°")
    label = label.replace("$\\circ$", "°")
    label = label.replace("^\\circ", "°")
    label = label.replace("^{\\circ}", "°")
    label = label.replace("\\circ", "°")

    # Replace other common LaTeX symbols
    label = label.replace("$\\mu$", "μ")
    label = label.replace("\\mu", "μ")
    label = label.replace("$\\alpha$", "α")
    label = label.replace("\\alpha", "α")
    label = label.replace("$\\beta$", "β")
    label = label.replace("\\beta", "β")
    label = label.replace("$\\gamma$", "γ")
    label = label.replace("\\gamma", "γ")
    label = label.replace("$\\delta$", "δ")
    label = label.replace("\\delta", "δ")
    label = label.replace("$\\theta$", "θ")
    label = label.replace("\\theta", "θ")
    label = label.replace("$\\phi$", "φ")
    label = label.replace("\\phi", "φ")
    label = label.replace("$\\pi$", "π")
    label = label.replace("\\pi", "π")
    label = label.replace("$\\sigma$", "σ")
    label = label.replace("\\sigma", "σ")
    label = label.replace("$\\omega$", "ω")
    label = label.replace("\\omega", "ω")

    # Remove any remaining LaTeX dollar signs
    label = label.replace("$", "")

    return label


class Plotter(SimulationComponent):

    type = "plotter"

    def __init__(self, config, name):
        super(Plotter, self).__init__(config, name)

        # print(f"Config: {config}")
        # print(f"Name: {name}")

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
        self.generate_plots()
        if (
            "interactiveDashboard" in self._config.keys()
            and self._config["interactiveDashboard"]
        ):
            self.create_interactive_dashboard()

    def generate_plots(self):
        self._log.info("Generating Plots.")

        # print(f"Data: {self._data}")

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

            # Initialize list to collect figures for simultaneous display
            figures_to_show = []
            if "show_plots" in self._config and self._config["show_plots"]:
                figures_to_show = []

            for plot_name, plot_config in self._config["plots"].items():
                plot_config["path"] = self._plots_path
                plot_config["plot_name"] = plot_name
                plot_config["merge_pdf"] = merge_pdf
                # Pass show_plots option from main config to individual plot configs
                if "show_plots" in self._config:
                    plot_config["show_plots"] = self._config["show_plots"]
                    plot_config["figures_to_show"] = figures_to_show
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

            # Show all plots simultaneously if requested
            if (
                "show_plots" in self._config
                and self._config["show_plots"]
                and figures_to_show
            ):
                self._log.info(
                    f"Showing {len(figures_to_show)} plots simultaneously..."
                )
                plt.show()

        self._log.info(f"Plots generated. View them at {self._output_path}")
        return True

    def create_interactive_dashboard(self):
        """Create an interactive multi-plot dashboard with synchronized zooming/panning"""
        if "plots" not in self._config.keys():
            self._log.warning("No plots configured for interactive dashboard")
            return

        # Collect plot data for multi-plot
        plots_data = []

        for plot_name, plot_config in self._config["plots"].items():
            if "type" in plot_config.keys() and plot_config["type"] == "time_series":
                # Prepare data for this plot
                plot_data = {
                    "title": plot_config["title"],
                    "vars": plot_config["vars"],
                    "data": self._data.copy(),
                    "legend": plot_config.get("legend", plot_config["vars"]),
                    "ylabel": plot_config.get(
                        "ylabel", "Value"
                    ),  # Add ylabel for better labeling
                }

                # Add textfields if they exist
                if "textfields" in plot_config:
                    plot_data["textfields"] = plot_config["textfields"]

                # Convert units if specified
                if "xUnit" in plot_config.keys():
                    plot_data["data"] = convert_units(
                        plot_data["data"], ["time"], plot_config["xUnit"]
                    )
                if "yUnit" in plot_config.keys():
                    plot_data["data"] = convert_units(
                        plot_data["data"], plot_config["vars"], plot_config["yUnit"]
                    )

                plots_data.append(plot_data)

        if not plots_data:
            self._log.warning("No time series plots found for interactive dashboard")
            return

        self._log.info(
            f"Creating interactive dashboard with {len(plots_data)} plots..."
        )

        # Create multi-plot dashboard
        multi_plot = PlotlyMultiPlot(plots_data, self._config)
        fig = multi_plot.create_multi_plot()

        # Save interactive dashboard
        dashboard_path = os.path.join(self._output_path, "interactive_dashboard.html")
        pyo.plot(fig, filename=dashboard_path, auto_open=False)

        self._log.info(f"Interactive dashboard saved to: {dashboard_path}")
        self._log.info(
            f"Dashboard contains {len(plots_data)} plots with synchronized x-axis zooming"
        )

        # Automatically open in browser
        try:
            webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")
            self._log.info("Opened interactive dashboard in browser")
        except Exception as e:
            self._log.warning(f"Could not automatically open browser: {e}")
            self._log.info(f"Please manually open: {dashboard_path}")

        return fig


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
    # Energy
    elif from_unit == "J" and to_unit == "kWh":
        conversion_factor = 1 / 3600000
    elif from_unit == "kWh" and to_unit == "J":
        conversion_factor = 3600000
    # Gradient
    elif from_unit == "K/s" and to_unit == "K/h":
        conversion_factor = 3600
    elif from_unit == "K/h" and to_unit == "K/s":
        conversion_factor = 1 / 3600

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

        # Clean axis labels to use proper Unicode symbols
        xlabel = clean_axis_label(self._config["xlabel"])
        ylabel = clean_axis_label(self._config["ylabel"])
        title = clean_axis_label(self._config["title"])

        ax.set(
            xlabel=xlabel,
            ylabel=ylabel,
            title=title,
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

        # Save individual files FIRST (before showing plots)
        for filetype in filetypes:
            fig.savefig(
                self._config["path"]
                + "/"
                + self._title.replace(" ", "_")
                + "."
                + filetype
            )

        # Store figure for later display if show_plots is enabled
        if "show_plots" in self._config and self._config["show_plots"]:
            # Don't close the figure, let the plotter handle it
            if "figures_to_show" in self._config:
                self._config["figures_to_show"].append(fig)
        else:
            plt.close(fig)


class TimeSeriesPlot(BasePlot):
    """Time series plot"""

    def __init__(self, data, config):
        super().__init__(data, config)

    def generate(self):
        fig, ax = plt.subplots(figsize=(40, 5))
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
        # Handle textfields
        if "textfields" in self._config:
            for textfield_config in self._config["textfields"]:
                self._add_textfield(ax, textfield_config)

        self.finalize(fig, ax)

    def _add_textfield(self, ax, textfield_config):
        """Add a single textfield to the plot"""
        prefix = textfield_config.get("prefix", "")
        var = textfield_config.get("var", "time")
        round_digits = textfield_config.get("round", 2)
        suffix = textfield_config.get("suffix", "")

        if "unit" in textfield_config:
            self._data = convert_units(self._data, [var], textfield_config["unit"])

        value = self._data[var][-1] if var in self._data else ""

        text = f"{prefix}{value:.{round_digits}f}{suffix}"
        x = textfield_config.get("x", 0.05)
        y = textfield_config.get("y", 0.95)
        fontsize = textfield_config.get("fontsize", 10)
        ax.text(
            x,
            y,
            text,
            transform=ax.transAxes,
            fontsize=fontsize,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
        )


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


class PlotlyInteractivePlot(BasePlot):
    """Interactive Plotly plot with synchronized zooming and panning"""

    def __init__(self, data, config):
        super().__init__(data, config)

    def generate(self):
        # Convert units if specified
        if "xUnit" in self._config.keys():
            self._data = convert_units(self._data, ["time"], self._config["xUnit"])
        if "yUnit" in self._config.keys():
            self._data = convert_units(
                self._data, self._config["vars"], self._config["yUnit"]
            )

        # Create the plot
        fig = go.Figure()

        # Add traces for each variable
        for i, var in enumerate(self._config["vars"]):
            legend_name = (
                self._config["legend"][i]
                if "legend" in self._config.keys() and i < len(self._config["legend"])
                else var
            )

            fig.add_trace(
                go.Scatter(
                    x=self._data["time"],
                    y=self._data[var],
                    name=legend_name,
                    mode="lines",
                    line=dict(width=2),
                    hovertemplate=f"<b>{legend_name}</b><br>"
                    + "Time: %{x}<br>"
                    + "Value: %{y}<extra></extra>",
                )
            )

        # Update layout with better styling
        fig.update_layout(
            title=dict(
                text=clean_axis_label(self._config["title"]),
                x=0.5,
                xanchor="center",
                font=dict(size=16),
            ),
            xaxis_title=clean_axis_label(self._config.get("xlabel", "Time")),
            yaxis_title=clean_axis_label(self._config.get("ylabel", "Value")),
            hovermode="x unified",
            showlegend=True,
            height=500,
            width=1000,
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="lightgray",
                borderwidth=1,
            ),
            margin=dict(l=50, r=50, t=80, b=50),
        )

        # Update axes for better appearance
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
            zeroline=False,
            showline=True,
            linewidth=1,
            linecolor="black",
        )

        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
            zeroline=False,
            showline=True,
            linewidth=1,
            linecolor="black",
        )

        # Set axis limits if specified
        if "limits" in self._config.keys():
            if "x" in self._config["limits"]:
                fig.update_xaxes(range=self._config["limits"]["x"])
            if "y" in self._config["limits"]:
                fig.update_yaxes(range=self._config["limits"]["y"])

        # Handle textfields
        if "textfields" in self._config:
            for textfield_config in self._config["textfields"]:
                self._add_textfield_plotly(fig, textfield_config)

        # Save as HTML file
        output_path = os.path.join(
            self._config["path"], self._title.replace(" ", "_") + "_interactive.html"
        )
        pyo.plot(fig, filename=output_path, auto_open=False)

        # Store the figure for later display
        if "figures_to_show" in self._config:
            self._config["figures_to_show"].append(fig)

    def _add_textfield_plotly(self, fig, textfield_config):
        """Add a single textfield annotation to the Plotly plot"""
        prefix = textfield_config.get("prefix", "")
        var = textfield_config.get("var", "time")
        round_digits = textfield_config.get("round", 2)
        suffix = textfield_config.get("suffix", "")

        if "unit" in textfield_config:
            self._data = convert_units(self._data, [var], textfield_config["unit"])

        value = self._data[var][-1] if var in self._data else ""

        text = f"{prefix}{value:.{round_digits}f}{suffix}"
        x = textfield_config.get("x", 0.05)
        y = textfield_config.get("y", 0.95)
        fontsize = textfield_config.get("fontsize", 10)

        # Convert relative coordinates to absolute coordinates for Plotly
        # Plotly uses absolute coordinates (0-1) for annotations
        x_abs = x
        y_abs = y

        # Add annotation to the figure
        fig.add_annotation(
            x=x_abs,
            y=y_abs,
            xref="paper",  # Use paper coordinates (0-1)
            yref="paper",  # Use paper coordinates (0-1)
            text=text,
            showarrow=False,
            font=dict(size=fontsize),
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="lightgray",
            borderwidth=1,
            align="left",
            xanchor="left",
            yanchor="top",
        )


class PlotlyMultiPlot:
    """Class to create interactive multi-plot layouts with synchronized interactions"""

    def __init__(self, plots_data, config):
        self._plots_data = plots_data
        self._config = config
        import logging

        self._log = logging.getLogger(self.__class__.__name__)

    def create_multi_plot(self):
        """Create a multi-plot layout with synchronized zooming/panning"""
        # Create subplot figure with one plot per row
        n_plots = len(self._plots_data)

        # No limit on number of plots - handle all plots
        plots_to_use = self._plots_data

        # Calculate appropriate vertical spacing based on number of plots
        # Use a fixed small spacing that works well for many plots
        vertical_spacing = 0.02

        # Create subplot figure - one plot per row, one column
        fig = make_subplots(
            rows=n_plots,
            cols=1,
            subplot_titles=[
                clean_axis_label(plot_data["title"]) for plot_data in plots_to_use
            ],
            shared_xaxes=True,  # This enables synchronized time axis zooming
            vertical_spacing=vertical_spacing,
            specs=[[{"secondary_y": False}] for _ in range(n_plots)],
        )

        # Define a consistent color palette for all plots
        color_palette = (
            plotly.colors.qualitative.Set1
            + plotly.colors.qualitative.Set2
            + plotly.colors.qualitative.Set3
        )

        # Add traces for each plot
        for i, plot_data in enumerate(plots_to_use):
            row = i + 1  # 1-indexed for plotly

            for j, var in enumerate(plot_data["vars"]):
                legend_name = (
                    plot_data["legend"][j]
                    if "legend" in plot_data and j < len(plot_data["legend"])
                    else var
                )

                # Use consistent colors across all plots
                color_index = j % len(color_palette)
                color = color_palette[color_index]

                # Create the trace with consistent colors
                trace = go.Scatter(
                    x=plot_data["data"]["time"],
                    y=plot_data["data"][var],
                    name=legend_name,
                    mode="lines",
                    line=dict(
                        width=1.5,
                        color=color,
                    ),
                    showlegend=True,
                    hovertemplate=f"<b>{legend_name}</b><br>"
                    + "Time: %{x}<br>"
                    + "Value: %{y}<extra></extra>",
                    legendgroup=f"plot_{i}",  # Group legends by plot
                    legendgrouptitle_text=clean_axis_label(
                        plot_data["title"]
                    ),  # Group title for each plot
                )

                fig.add_trace(trace, row=row, col=1)

            # Handle textfields for this plot if they exist
            if "textfields" in plot_data:
                for textfield_config in plot_data["textfields"]:
                    self._add_textfield_multi_plot(
                        fig, textfield_config, row, plot_data["data"]
                    )

        # Calculate height based on number of plots (minimum 300px per plot)
        plot_height = max(300, 8000 // n_plots)  # Ensure minimum height per plot
        total_height = plot_height * n_plots

        # Update layout for better appearance
        fig.update_layout(
            title="Interactive Multi-Plot Dashboard",
            height=total_height,
            width=None,  # Full width - will adapt to browser window
            hovermode="x unified",
            showlegend=True,
            margin=dict(l=50, r=50, t=100, b=50),
            legend=dict(
                groupclick="toggleitem",  # Allow clicking on legend groups
                bgcolor="rgba(255,255,255,0.9)",
                bordercolor="lightgray",
                borderwidth=1,
            ),
        )

        # Update all subplot axes for better appearance
        for i in range(1, n_plots + 1):
            # X-axis (time) - synchronized across all plots
            fig.update_xaxes(
                title_text="Time",
                row=i,
                col=1,
                showgrid=True,
                gridwidth=1,
                gridcolor="lightgray",
                zeroline=False,
                showline=True,
                linewidth=1,
                linecolor="black",
            )

            # Y-axis - individual for each plot
            ylabel = plots_to_use[i - 1].get("ylabel", "Value")
            fig.update_yaxes(
                title_text=clean_axis_label(ylabel),
                row=i,
                col=1,
                showgrid=True,
                gridwidth=1,
                gridcolor="lightgray",
                zeroline=False,
                showline=True,
                linewidth=1,
                linecolor="black",
            )

        # Synchronize all x-axes (time axis) for zooming and panning
        # This ensures that when you zoom/pan on one plot, all others follow
        fig.update_xaxes(matches="x")

        # Don't synchronize y-axes - each plot keeps its own scale
        # This allows each plot to have its own y-axis range

        return fig

    def _add_textfield_multi_plot(self, fig, textfield_config, row, data):
        """Add a single textfield annotation to a specific subplot in the multi-plot"""
        prefix = textfield_config.get("prefix", "")
        var = textfield_config.get("var", "time")
        round_digits = textfield_config.get("round", 2)
        suffix = textfield_config.get("suffix", "")

        if "unit" in textfield_config:
            data = convert_units(data, [var], textfield_config["unit"])

        value = data[var][-1] if var in data else ""

        text = f"{prefix}{value:.{round_digits}f}{suffix}"
        x = textfield_config.get("x", 0.05)
        y = textfield_config.get("y", 0.95)
        fontsize = textfield_config.get("fontsize", 10)

        # For multi-plot, we need to position the annotation relative to the specific subplot
        # Convert the relative coordinates to the subplot's coordinate system
        x_abs = x
        y_abs = y

        # Add annotation to the specific subplot
        fig.add_annotation(
            x=x_abs,
            y=y_abs,
            xref=f"x{row}",  # Reference the specific subplot's x-axis
            yref=f"y{row}",  # Reference the specific subplot's y-axis
            text=text,
            showarrow=False,
            font=dict(size=fontsize),
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="lightgray",
            borderwidth=1,
            align="left",
            xanchor="left",
            yanchor="top",
        )


class PlotFactory:
    """Factory class for creating plots"""

    plot_types = {
        "time_series": TimeSeriesPlot,
        "scatter": ScatterPlot,
        "plotly_interactive": PlotlyInteractivePlot,
    }

    @staticmethod
    def instantiate_plot(plot_type, data, config):
        if plot_type in PlotFactory.plot_types:
            return PlotFactory.plot_types[plot_type](data, config)
        else:
            raise NotImplementedError(f"Plot type {plot_type} not implemented")
