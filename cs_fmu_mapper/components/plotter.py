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
import matplotlib.patches as patches
from matplotlib.table import Table


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


def format_number(
    value, round_digits=2, use_scientific=False, scientific_threshold=1e6
):
    """Format a number with optional scientific notation support

    Args:
        value: The numeric value to format
        round_digits: Number of decimal places (default: 2)
        use_scientific: Whether to use scientific notation (default: False)
        scientific_threshold: Threshold above which to use scientific notation (default: 1e6)

    Returns:
        Formatted string representation of the number
    """
    try:
        numeric_value = float(value)

        # Use scientific notation if explicitly requested or if value exceeds threshold
        if use_scientific or abs(numeric_value) >= scientific_threshold:
            return f"{numeric_value:.{round_digits}e}"
        else:
            return f"{numeric_value:.{round_digits}f}"
    except (TypeError, ValueError):
        return str(value)


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
        table_plots = []

        for plot_name, plot_config in self._config["plots"].items():
            if "type" in plot_config.keys():
                if plot_config["type"] == "time_series":
                    # Prepare data for time series plot
                    plot_data = {
                        "title": plot_config["title"],
                        "vars": plot_config["vars"],
                        "data": self._data.copy(),
                        "legend": plot_config.get("legend", plot_config["vars"]),
                        "ylabel": plot_config.get("ylabel", "Value"),
                        "xlabel": plot_config.get("xlabel", "Time"),
                        "type": "time_series",
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

                elif plot_config["type"] == "table":
                    # Store table plots separately
                    table_plots.append(plot_config)

        if not plots_data and not table_plots:
            self._log.warning("No plots found for interactive dashboard")
            return

        # Count time series and table plots
        time_series_count = sum(1 for p in plots_data if p.get("type") == "time_series")
        table_count = len(table_plots)

        self._log.info(
            f"Creating interactive dashboard with {time_series_count} time series plots and {table_count} table plots..."
        )

        # Create separate figures for time series plots and tables
        if plots_data:
            # Create multi-plot for time series plots
            multi_plot = PlotlyMultiPlot(plots_data, self._config)
            time_series_fig = multi_plot.create_multi_plot()
        else:
            time_series_fig = None

        # Create separate figure for tables
        if table_plots:
            # Prepare all table data first
            prepared_tables = [
                (table_plot, self._prepare_table_data_for_dashboard(table_plot))
                for table_plot in table_plots
            ]

            # Compute dynamic heights per table (base + per-row)
            per_table_heights = []
            for _, td in prepared_tables:
                rows = len(td["data"]) if td["data"] else 1
                per_table_heights.append(200 + rows * 40)

            total_height = max(sum(per_table_heights), 300)
            # Normalize for row_heights; avoid zero division
            height_sum = sum(per_table_heights) if sum(per_table_heights) > 0 else 1
            row_heights = [h / height_sum for h in per_table_heights]

            # Create subplots: one row per table, with per-table titles from config
            table_fig = make_subplots(
                rows=len(prepared_tables),
                cols=1,
                specs=[[{"type": "table"}] for _ in prepared_tables],
                subplot_titles=[
                    clean_axis_label(tp.get("title", f"Table {i+1}"))
                    for i, (tp, _) in enumerate(prepared_tables)
                ],
                vertical_spacing=0.08,
                row_heights=row_heights,
                shared_xaxes=False,
            )

            # Add each table as its own subplot
            for i, (table_plot, table_data) in enumerate(prepared_tables):
                # Transpose rows -> columns for Plotly Table
                if table_data["data"]:
                    columns_data = list(map(list, zip(*table_data["data"])))
                else:
                    columns_data = [[] for _ in table_data["headers"]]

                # Apply styling from table_properties
                table_props = table_plot.get("table_properties", {})
                header_color = table_props.get("header_color", "#4CAF50")
                row_colors = table_props.get(
                    "row_colors", ["#f2f2f2"]
                )  # default single color
                font_size = table_props.get("font_size", 11)
                row_height_scale = table_props.get("row_height", None)
                # Map scale to pixels if provided
                cells_height = (
                    int(18 * row_height_scale)
                    if isinstance(row_height_scale, (int, float))
                    else None
                )
                nrows = len(table_data["data"]) if table_data["data"] else 0
                ncols = len(table_data["headers"]) if table_data["headers"] else 0
                if nrows > 0 and ncols > 0:
                    alternating_colors = [
                        row_colors[r % len(row_colors)] for r in range(nrows)
                    ]
                    cells_fill_color = [list(alternating_colors) for _ in range(ncols)]
                else:
                    cells_fill_color = row_colors[0] if row_colors else "#f2f2f2"

                # Optional column widths
                column_widths = table_props.get("column_widths")
                if isinstance(column_widths, list) and ncols > 0:
                    if len(column_widths) < ncols:
                        column_widths = column_widths + [1] * (
                            ncols - len(column_widths)
                        )
                    elif len(column_widths) > ncols:
                        column_widths = column_widths[:ncols]
                else:
                    column_widths = None

                table_fig.add_trace(
                    go.Table(
                        columnwidth=column_widths,
                        header=dict(
                            values=table_data["headers"],
                            fill_color=header_color,
                            align="center",
                            line_color=table_props.get("grid_color", "#CCCCCC"),
                            line_width=table_props.get("grid_width", 1),
                            font=dict(color="white", size=font_size),
                        ),
                        cells=dict(
                            values=columns_data,
                            fill_color=cells_fill_color,
                            align="center",
                            line_color=table_props.get("grid_color", "#CCCCCC"),
                            line_width=table_props.get("grid_width", 1),
                            font=dict(size=font_size),
                            height=cells_height,
                        ),
                    ),
                    row=i + 1,
                    col=1,
                )

            # Update layout (use overall height; individual titles are set as subplot_titles)
            table_fig.update_layout(
                height=total_height,
                width=None,
                margin=dict(l=50, r=50, t=80, b=50),
                showlegend=False,
            )
        else:
            table_fig = None

        # Save interactive dashboard
        dashboard_path = os.path.join(self._output_path, "interactive_dashboard.html")

        # Create HTML with both figures
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Interactive Dashboard</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .plot-container { margin-bottom: 30px; }
                h1 { color: #333; text-align: center; }
                h2 { color: #555; margin-top: 30px; }
            </style>
        </head>
        <body>
            <h1>Interactive Dashboard</h1>
        """

        if time_series_fig:
            # Convert figure to JSON and embed in HTML
            time_series_json = time_series_fig.to_json()
            html_content += f"""
            <div class="plot-container">
                <h2>Time Series Plots</h2>
                <div id="timeSeriesPlot"></div>
            </div>
            <script>
                var timeSeriesData = {time_series_json};
                Plotly.newPlot('timeSeriesPlot', timeSeriesData.data, timeSeriesData.layout);
            </script>
            """

        if table_fig:
            # Convert figure to JSON and embed in HTML
            table_json = table_fig.to_json()
            html_content += f"""
            <div class="plot-container">
                <h2>Data Tables</h2>
                <div id="tablePlot"></div>
            </div>
            <script>
                var tableData = {table_json};
                Plotly.newPlot('tablePlot', tableData.data, tableData.layout);
            </script>
            """

        html_content += """
        </body>
        </html>
        """

        with open(dashboard_path, "w") as f:
            f.write(html_content)

        self._log.info(f"Interactive dashboard saved to: {dashboard_path}")
        self._log.info(
            f"Dashboard contains {time_series_count} time series plots with synchronized x-axis zooming and {table_count} table plots"
        )

        # Automatically open in browser
        try:
            webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")
            self._log.info("Opened interactive dashboard in browser")
        except Exception as e:
            self._log.warning(f"Could not automatically open browser: {e}")
            self._log.info(f"Please manually open: {dashboard_path}")

        return time_series_fig if time_series_fig else table_fig

    def _prepare_table_data_for_dashboard(self, table_plot):
        """Prepare table data for dashboard tables (combine loop and manual rows)"""
        headers = None
        data: list[list[str]] = []

        # Loop rows first (if any)
        if "loop_data" in table_plot:
            loop_config = table_plot["loop_data"]
            loop_headers = loop_config.get("headers", ["Description", "Value", "Unit"])
            headers = headers or loop_headers

            loop_var = loop_config.get("loop_var", [])
            if not loop_var:
                data.append(["No loop data specified", "", ""])  # placeholder
            else:
                rows = []
                for item in loop_var:
                    row_data = []
                    for col_template in loop_config.get("columns", []):
                        if isinstance(col_template, dict):
                            if "template" in col_template:
                                template = col_template["template"]
                                processed_value = template.replace(
                                    "{{item}}", str(item)
                                ).replace("{item}", str(item))

                                if "var_template" in col_template:
                                    var_template = col_template["var_template"]
                                    var_name = var_template.replace(
                                        "{{item}}", str(item)
                                    ).replace("{item}", str(item))
                                    if (
                                        var_name in self._data
                                        and len(self._data[var_name]) > 0
                                    ):
                                        value = self._data[var_name][-1]
                                        if "unit" in col_template:
                                            temp_data = {var_name: [value]}
                                            temp_data = convert_units(
                                                temp_data,
                                                [var_name],
                                                col_template["unit"],
                                            )
                                            value = temp_data[var_name][0]
                                        round_digits = col_template.get("round", 2)
                                        use_scientific = col_template.get(
                                            "use_scientific", False
                                        )
                                        scientific_threshold = col_template.get(
                                            "scientific_threshold", 1e6
                                        )
                                        value = format_number(
                                            value,
                                            round_digits,
                                            use_scientific,
                                            scientific_threshold,
                                        )
                                        prefix = col_template.get("prefix", "")
                                        suffix = col_template.get("suffix", "")
                                        value = f"{prefix}{value}{suffix}"
                                        processed_value = processed_value.replace(
                                            "{{value}}", str(value)
                                        ).replace("{value}", str(value))
                                    else:
                                        processed_value = processed_value.replace(
                                            "{{value}}",
                                            col_template.get("default", "N/A"),
                                        ).replace(
                                            "{value}",
                                            col_template.get("default", "N/A"),
                                        )

                                row_data.append(processed_value)
                            else:
                                row_data.append(col_template.get("value", ""))
                        else:
                            row_data.append(str(col_template))
                    rows.append(row_data)
                data.extend(rows)

        # Manual rows next (if any)
        if "manual_data" in table_plot:
            manual_data = table_plot["manual_data"]
            manual_headers = manual_data.get(
                "headers", ["Description", "Value", "Unit"]
            )
            headers = headers or manual_headers

            rows = []
            for row in manual_data.get("rows", []):
                row_data = []
                for col in row:
                    if isinstance(col, dict):
                        if "var" in col:
                            var_name = col["var"]
                            if var_name in self._data and len(self._data[var_name]) > 0:
                                value = self._data[var_name][-1]
                                if "unit" in col:
                                    temp_data = {var_name: [value]}
                                    temp_data = convert_units(
                                        temp_data, [var_name], col["unit"]
                                    )
                                    value = temp_data[var_name][0]
                                round_digits = col.get("round", 2)
                                use_scientific = col.get("use_scientific", False)
                                scientific_threshold = col.get(
                                    "scientific_threshold", 1e6
                                )
                                value = format_number(
                                    value,
                                    round_digits,
                                    use_scientific,
                                    scientific_threshold,
                                )
                                prefix = col.get("prefix", "")
                                suffix = col.get("suffix", "")
                                value = f"{prefix}{value}{suffix}"
                                row_data.append(value)
                            else:
                                row_data.append(col.get("default", "N/A"))
                        else:
                            row_data.append(col.get("value", ""))
                    else:
                        row_data.append(str(col))
                rows.append(row_data)
            data.extend(rows)

        # Fallbacks and normalization
        if headers is None:
            headers = ["Description", "Value", "Unit"]
        expected_cols = len(headers)
        normalized = []
        for row in data:
            if len(row) < expected_cols:
                normalized.append(row + [""] * (expected_cols - len(row)))
            else:
                normalized.append(row[:expected_cols])

        if not normalized:
            normalized = [["No data available", "", ""]]

        return {"headers": headers, "data": normalized}


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
        # Handle cases where xlabel/ylabel might not be configured (e.g., table plots)
        xlabel = clean_axis_label(self._config.get("xlabel", ""))
        ylabel = clean_axis_label(self._config.get("ylabel", ""))
        title = clean_axis_label(self._config["title"])

        # Only set labels if they are provided
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        ax.set_title(title)

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

        # Obtain last value safely, with optional unit conversion on a temp value
        if var in self._data and len(self._data[var]) > 0:
            value = self._data[var][-1]
            if "unit" in textfield_config:
                temp_data = {var: [value]}
                temp_data = convert_units(temp_data, [var], textfield_config["unit"])
                value = temp_data[var][0]
        else:
            value = textfield_config.get("default", "N/A")

        # Format number if possible, else use string representation
        try:
            numeric_value = float(value)
            use_scientific = textfield_config.get("use_scientific", False)
            scientific_threshold = textfield_config.get("scientific_threshold", 1e6)
            formatted_value = format_number(
                numeric_value, round_digits, use_scientific, scientific_threshold
            )
        except (TypeError, ValueError):
            formatted_value = str(value)

        text = f"{prefix}{formatted_value}{suffix}"
        x = textfield_config.get("x", 0.05)
        y = textfield_config.get("y", 0.95)
        fontsize = textfield_config.get("fontsize", 10)
        ax.text(
            x,
            y,
            text,
            fontsize=fontsize,
            verticalalignment="top",
            transform=ax.transAxes,
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
            showticklabels=True,
            tickmode="auto",
            nticks=10,
            tickformat=".1f",
            tickangle=0,
        )

        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
            zeroline=False,
            showline=True,
            linewidth=1,
            linecolor="black",
            showticklabels=True,
            tickmode="auto",
            nticks=8,
            tickformat=".2f",
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

        # Obtain last value safely, with optional unit conversion on a temp value
        if var in self._data and len(self._data[var]) > 0:
            value = self._data[var][-1]
            if "unit" in textfield_config:
                temp_data = {var: [value]}
                temp_data = convert_units(temp_data, [var], textfield_config["unit"])
                value = temp_data[var][0]
        else:
            value = textfield_config.get("default", "N/A")

        # Format number if possible, else use string representation
        try:
            numeric_value = float(value)
            use_scientific = textfield_config.get("use_scientific", False)
            scientific_threshold = textfield_config.get("scientific_threshold", 1e6)
            formatted_value = format_number(
                numeric_value, round_digits, use_scientific, scientific_threshold
            )
        except (TypeError, ValueError):
            formatted_value = str(value)

        text = f"{prefix}{formatted_value}{suffix}"
        x = textfield_config.get("x", 0.05)
        y = textfield_config.get("y", 0.95)
        fontsize = textfield_config.get("fontsize", 10)

        # Add annotation relative to the plot's data area (domain)
        fig.add_annotation(
            x=x,
            y=y,
            xref="x domain",
            yref="y domain",
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


class TablePlot(BasePlot):
    """Table plot for displaying values and descriptions"""

    def __init__(self, data, config):
        super().__init__(data, config)

    def generate(self):
        # Prepare table data
        table_data = self._prepare_table_data()

        # Ensure we have valid data before creating the table
        if not table_data["data"] or len(table_data["data"]) == 0:
            # Create a simple figure with a message instead of a table
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.axis("off")
            ax.text(
                0.5,
                0.5,
                "No data available for table",
                ha="center",
                va="center",
                fontsize=16,
                transform=ax.transAxes,
            )
            ax.set_title(self._title, pad=20, fontsize=16, fontweight="bold")
            self.finalize(fig, ax, filetypes=["pdf", "png"])
            return

        # Ensure we have at least one row with data
        has_data = False
        for row in table_data["data"]:
            if any(cell != "" and cell != "N/A" for cell in row):
                has_data = True
                break

        if not has_data:
            # Create a simple figure with a message instead of a table
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.axis("off")
            ax.text(
                0.5,
                0.5,
                "No data available for table",
                ha="center",
                va="center",
                fontsize=16,
                transform=ax.transAxes,
            )
            ax.set_title(self._title, pad=20, fontsize=16, fontweight="bold")
            self.finalize(fig, ax, filetypes=["pdf", "png"])
            return

        # Validate that all rows have the same number of columns
        expected_cols = len(table_data["headers"])
        for i, row in enumerate(table_data["data"]):
            if len(row) != expected_cols:
                # Pad or truncate row to match header length
                if len(row) < expected_cols:
                    table_data["data"][i] = row + [""] * (expected_cols - len(row))
                else:
                    table_data["data"][i] = row[:expected_cols]

        # Create figure and axis
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.axis("tight")
        ax.axis("off")

        # Create table
        table = ax.table(
            cellText=table_data["data"],
            colLabels=table_data["headers"],
            cellLoc="center",
            loc="center",
            bbox=[0, 0, 1, 1],
        )

        # Style the table
        self._style_table(table)

        # Set title
        ax.set_title(self._title, pad=20, fontsize=16, fontweight="bold")

        self.finalize(fig, ax, filetypes=["pdf", "png"])

    def _prepare_table_data(self):
        """Prepare table data from configuration. Supports combining loop_data and manual_data."""
        headers = None
        data: list[list[str]] = []

        # 1) Loop rows (if any)
        if "loop_data" in self._config:
            loop_config = self._config["loop_data"]
            loop_headers = loop_config.get("headers", ["Description", "Value", "Unit"])
            headers = headers or loop_headers

            loop_var = loop_config.get("loop_var", [])
            if not loop_var:
                data.append(["No loop data specified", "", ""])  # placeholder row
            else:
                rows = []
                for item in loop_var:
                    row_data = []
                    for col_template in loop_config.get("columns", []):
                        if isinstance(col_template, dict):
                            if "template" in col_template:
                                template = col_template["template"]
                                processed_value = (
                                    template.replace("{{item}}", str(item))
                                    .replace("{item}", str(item))
                                    .replace("{value}", str(item))
                                )

                                if "var_template" in col_template:
                                    var_template = col_template["var_template"]
                                    var_name = var_template.replace(
                                        "{{item}}", str(item)
                                    ).replace("{item}", str(item))
                                    if (
                                        var_name in self._data
                                        and len(self._data[var_name]) > 0
                                    ):
                                        value = self._data[var_name][-1]
                                        if "unit" in col_template:
                                            temp_data = {var_name: [value]}
                                            temp_data = convert_units(
                                                temp_data,
                                                [var_name],
                                                col_template["unit"],
                                            )
                                            value = temp_data[var_name][0]
                                        round_digits = col_template.get("round", 2)
                                        use_scientific = col_template.get(
                                            "use_scientific", False
                                        )
                                        scientific_threshold = col_template.get(
                                            "scientific_threshold", 1e6
                                        )
                                        value = format_number(
                                            value,
                                            round_digits,
                                            use_scientific,
                                            scientific_threshold,
                                        )
                                        prefix = col_template.get("prefix", "")
                                        suffix = col_template.get("suffix", "")
                                        value = f"{prefix}{value}{suffix}"
                                        processed_value = processed_value.replace(
                                            "{{value}}", str(value)
                                        ).replace("{value}", str(value))
                                    else:
                                        processed_value = processed_value.replace(
                                            "{{value}}",
                                            col_template.get("default", "N/A"),
                                        ).replace(
                                            "{value}",
                                            col_template.get("default", "N/A"),
                                        )

                                row_data.append(processed_value)
                            else:
                                row_data.append(col_template.get("value", ""))
                        else:
                            row_data.append(str(col_template))
                    rows.append(row_data)
                data.extend(rows)

        # 2) Manual rows (if any)
        if "manual_data" in self._config:
            manual_data = self._config["manual_data"]
            manual_headers = manual_data.get(
                "headers", ["Description", "Value", "Unit"]
            )
            headers = headers or manual_headers

            rows = []
            for row in manual_data.get("rows", []):
                row_data = []
                for col in row:
                    if isinstance(col, dict):
                        if "var" in col:
                            var_name = col["var"]
                            if var_name in self._data and len(self._data[var_name]) > 0:
                                value = self._data[var_name][-1]
                                if "unit" in col:
                                    temp_data = {var_name: [value]}
                                    temp_data = convert_units(
                                        temp_data, [var_name], col["unit"]
                                    )
                                    value = temp_data[var_name][0]
                                round_digits = col.get("round", 2)
                                use_scientific = col.get("use_scientific", False)
                                scientific_threshold = col.get(
                                    "scientific_threshold", 1e6
                                )
                                value = format_number(
                                    value,
                                    round_digits,
                                    use_scientific,
                                    scientific_threshold,
                                )
                                prefix = col.get("prefix", "")
                                suffix = col.get("suffix", "")
                                value = f"{prefix}{value}{suffix}"
                                row_data.append(value)
                            else:
                                row_data.append(col.get("default", "N/A"))
                        else:
                            row_data.append(col.get("value", ""))
                    else:
                        row_data.append(str(col))
                rows.append(row_data)
            data.extend(rows)

        # 3) Fallbacks
        if headers is None:
            headers = ["Description", "Value", "Unit"]
        if not data:
            data = [["No data available", "", ""]]

        return {"headers": headers, "data": data}

    def _style_table(self, table):
        """Apply styling to the table"""
        try:
            table_props = self._config.get("table_properties", {})

            # Access cells as dict of (row, col) -> Cell
            cells = (
                table.get_celld()
                if hasattr(table, "get_celld")
                else getattr(table, "_cells", None)
            )
            if not cells:
                return

            # Determine existing row and column indices
            row_indices = sorted({rc[0] for rc in cells.keys()})
            col_indices = sorted({rc[1] for rc in cells.keys()})
            if not row_indices or not col_indices:
                return

            header_row = min(row_indices)
            last_row = max(row_indices)

            # Colors and sizes
            header_color = table_props.get("header_color", "#4CAF50")
            row_colors = table_props.get("row_colors", ["#f2f2f2", "white"])
            font_size = table_props.get("font_size", 10)

            # Header styling
            for c in col_indices:
                cell = cells.get((header_row, c))
                if cell is not None:
                    cell.set_facecolor(header_color)
                    cell.set_text_props(weight="bold", color="white")

            # Body rows styling (alternating row colors)
            for r in row_indices:
                if r == header_row:
                    continue
                color = row_colors[(r - header_row) % len(row_colors)]
                for c in col_indices:
                    cell = cells.get((r, c))
                    if cell is not None:
                        cell.set_facecolor(color)
                        cell.set_text_props(size=font_size)

            # Optional: highlight the last row (e.g., manual summary)
            last_row_color = table_props.get("last_row_color")
            last_row_text_color = table_props.get("last_row_text_color")
            if last_row_color and last_row > header_row:
                for c in col_indices:
                    cell = cells.get((last_row, c))
                    if cell is not None:
                        cell.set_facecolor(last_row_color)
                        if last_row_text_color:
                            cell.set_text_props(
                                color=last_row_text_color, size=font_size
                            )

            # Optional: set column widths
            col_widths = table_props.get("column_widths")
            if isinstance(col_widths, list) and col_widths:
                for i, width in enumerate(col_widths):
                    for r in row_indices:
                        cell = cells.get((r, i))
                        if cell is not None:
                            cell.set_width(width)

            # General table properties
            table.auto_set_font_size(False)
            table.set_fontsize(font_size)
            table.scale(1, table_props.get("row_height", 2))

            # Grid line color/width and vertical centering
            grid_color = table_props.get("grid_color")
            grid_width = table_props.get("grid_width")
            for cell in cells.values():
                if grid_color is not None:
                    cell.set_edgecolor(grid_color)
                if grid_width is not None:
                    try:
                        cell.set_linewidth(float(grid_width))
                    except Exception:
                        pass
                try:
                    cell.get_text().set_va("center")
                    cell.get_text().set_ha("center")
                except Exception:
                    pass
        except Exception as e:
            # If any error occurs during styling, just return without styling
            # This prevents crashes and allows the table to be displayed without styling
            pass


class PlotlyTablePlot(BasePlot):
    """Interactive Plotly table plot mirroring TablePlot behavior"""

    def __init__(self, data, config):
        super().__init__(data, config)

    def generate(self):
        # Prepare table data
        table_data = self._prepare_table_data()

        # If no data, render a message figure
        if not table_data["data"] or len(table_data["data"]) == 0:
            fig = go.Figure()
            fig.add_annotation(
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                text="No data available for table",
                showarrow=False,
                font=dict(size=16),
            )
            fig.update_layout(
                title=dict(
                    text=clean_axis_label(self._title),
                    x=0.5,
                    xanchor="center",
                    font=dict(size=16),
                ),
                height=400,
                width=1000,
                margin=dict(l=50, r=50, t=80, b=50),
            )

            output_path = os.path.join(
                self._config["path"], self._title.replace(" ", "_") + "_table.html"
            )
            pyo.plot(fig, filename=output_path, auto_open=False)

            if "figures_to_show" in self._config:
                self._config["figures_to_show"].append(fig)
            return fig

        # Validate consistent column counts
        expected_cols = len(table_data["headers"])
        for i, row in enumerate(table_data["data"]):
            if len(row) != expected_cols:
                if len(row) < expected_cols:
                    table_data["data"][i] = row + [""] * (expected_cols - len(row))
                else:
                    table_data["data"][i] = row[:expected_cols]

        # Transpose rows to columns for Plotly Table
        columns_data = (
            list(map(list, zip(*table_data["data"])))
            if table_data["data"]
            else [[] for _ in table_data["headers"]]
        )

        # Apply styling from table_properties
        table_props = self._config.get("table_properties", {})
        header_color = table_props.get("header_color", "#4CAF50")
        row_colors = table_props.get("row_colors", ["#f2f2f2"])  # default single color
        font_size = table_props.get("font_size", 11)
        row_height_scale = table_props.get("row_height", None)
        cells_height = (
            int(18 * row_height_scale)
            if isinstance(row_height_scale, (int, float))
            else None
        )
        nrows = len(table_data["data"]) if table_data["data"] else 0
        ncols = len(table_data["headers"]) if table_data["headers"] else 0
        if nrows > 0 and ncols > 0:
            alternating_colors = [row_colors[r % len(row_colors)] for r in range(nrows)]
            cells_fill_color = [list(alternating_colors) for _ in range(ncols)]
        else:
            cells_fill_color = row_colors[0] if row_colors else "#f2f2f2"

        # Optional column widths
        column_widths = table_props.get("column_widths")
        if isinstance(column_widths, list) and ncols > 0:
            if len(column_widths) < ncols:
                column_widths = column_widths + [1] * (ncols - len(column_widths))
            elif len(column_widths) > ncols:
                column_widths = column_widths[:ncols]
        else:
            column_widths = None

        fig = go.Figure(
            data=[
                go.Table(
                    columnwidth=column_widths,
                    header=dict(
                        values=table_data["headers"],
                        fill_color=header_color,
                        align="center",
                        line_color=table_props.get("grid_color", "#CCCCCC"),
                        line_width=table_props.get("grid_width", 1),
                        font=dict(color="white", size=font_size),
                    ),
                    cells=dict(
                        values=columns_data,
                        fill_color=cells_fill_color,
                        align="center",
                        line_color=table_props.get("grid_color", "#CCCCCC"),
                        line_width=table_props.get("grid_width", 1),
                        font=dict(size=font_size),
                        height=cells_height,
                    ),
                )
            ]
        )

        fig.update_layout(
            title=dict(
                text=clean_axis_label(self._title),
                x=0.5,
                xanchor="center",
                font=dict(size=16),
            ),
            height=200 + len(table_data["data"]) * 40,
            width=1000,
            margin=dict(l=50, r=50, t=80, b=50),
        )

        output_path = os.path.join(
            self._config["path"], self._title.replace(" ", "_") + "_table.html"
        )
        pyo.plot(fig, filename=output_path, auto_open=False)

        if "figures_to_show" in self._config:
            self._config["figures_to_show"].append(fig)

        return fig

    def _prepare_table_data(self):
        """Prepare table data using the same semantics as TablePlot"""
        headers = []
        data = []

        # Manual configuration
        if "manual_data" in self._config:
            manual_data = self._config["manual_data"]
            headers = manual_data.get("headers", ["Description", "Value", "Unit"])

            rows = []
            for row in manual_data.get("rows", []):
                row_data = []
                for col in row:
                    if isinstance(col, dict):
                        if "var" in col:
                            var_name = col["var"]
                            if var_name in self._data and len(self._data[var_name]) > 0:
                                value = self._data[var_name][-1]

                                if "unit" in col:
                                    temp_data = {var_name: [value]}
                                    temp_data = convert_units(
                                        temp_data, [var_name], col["unit"]
                                    )
                                    value = temp_data[var_name][0]

                                round_digits = col.get("round", 2)
                                use_scientific = col.get("use_scientific", False)
                                scientific_threshold = col.get(
                                    "scientific_threshold", 1e6
                                )
                                value = format_number(
                                    value,
                                    round_digits,
                                    use_scientific,
                                    scientific_threshold,
                                )

                                prefix = col.get("prefix", "")
                                suffix = col.get("suffix", "")
                                value = f"{prefix}{value}{suffix}"

                                row_data.append(value)
                            else:
                                row_data.append(col.get("default", "N/A"))
                        else:
                            row_data.append(col.get("value", ""))
                    else:
                        row_data.append(str(col))
                rows.append(row_data)
            data = rows

        # Loop configuration
        elif "loop_data" in self._config:
            loop_config = self._config["loop_data"]
            headers = loop_config.get("headers", ["Description", "Value", "Unit"])
            loop_var = loop_config.get("loop_var", [])
            if not loop_var:
                data = [["No loop data specified", "", ""]]
            else:
                rows = []
                for item in loop_var:
                    row_data = []
                    for col_template in loop_config.get("columns", []):
                        if isinstance(col_template, dict):
                            if "template" in col_template:
                                template = col_template["template"]
                                processed_value = template.replace(
                                    "{{item}}", str(item)
                                ).replace("{item}", str(item))

                                if "var_template" in col_template:
                                    var_template = col_template["var_template"]
                                    var_name = var_template.replace(
                                        "{{item}}", str(item)
                                    ).replace("{item}", str(item))
                                    if (
                                        var_name in self._data
                                        and len(self._data[var_name]) > 0
                                    ):
                                        value = self._data[var_name][-1]

                                        if "unit" in col_template:
                                            temp_data = {var_name: [value]}
                                            temp_data = convert_units(
                                                temp_data,
                                                [var_name],
                                                col_template["unit"],
                                            )
                                            value = temp_data[var_name][0]

                                        round_digits = col_template.get("round", 2)
                                        use_scientific = col_template.get(
                                            "use_scientific", False
                                        )
                                        scientific_threshold = col_template.get(
                                            "scientific_threshold", 1e6
                                        )
                                        value = format_number(
                                            value,
                                            round_digits,
                                            use_scientific,
                                            scientific_threshold,
                                        )

                                        prefix = col_template.get("prefix", "")
                                        suffix = col_template.get("suffix", "")
                                        value = f"{prefix}{value}{suffix}"

                                        # Replace value placeholder in either style
                                        processed_value = processed_value.replace(
                                            "{{value}}", str(value)
                                        ).replace("{value}", str(value))
                                    else:
                                        processed_value = processed_value.replace(
                                            "{{value}}",
                                            col_template.get("default", "N/A"),
                                        ).replace(
                                            "{value}",
                                            col_template.get("default", "N/A"),
                                        )

                                row_data.append(processed_value)
                            else:
                                row_data.append(col_template.get("value", ""))
                        else:
                            row_data.append(str(col_template))
                    rows.append(row_data)
                data = rows

        else:
            headers = ["Description", "Value", "Unit"]
            data = [["No data specified", "", ""]]

        if not data:
            data = [["No data available", "", ""]]

        return {"headers": headers, "data": data}

    def _style_table(self, table):
        """Apply styling to the table (header, alternating rows, optional last-row highlight)."""
        try:
            table_props = self._config.get("table_properties", {})

            # Prefer public accessor for cells
            cells = (
                table.get_celld()
                if hasattr(table, "get_celld")
                else getattr(table, "_cells", None)
            )
            if not cells:
                return

            # Discover row/col indices
            row_indices = sorted({rc[0] for rc in cells.keys()})
            col_indices = sorted({rc[1] for rc in cells.keys()})
            if not row_indices or not col_indices:
                return

            header_row = min(row_indices)
            last_row = max(row_indices)

            header_color = table_props.get("header_color", "#4CAF50")
            row_colors = table_props.get("row_colors", ["#f2f2f2", "white"])
            font_size = table_props.get("font_size", 10)

            # Header styling
            for c in col_indices:
                cell = cells.get((header_row, c))
                if cell is not None:
                    cell.set_facecolor(header_color)
                    cell.set_text_props(weight="bold", color="white")

            # Alternating row colors for body
            for r in row_indices:
                if r == header_row:
                    continue
                color = row_colors[(r - header_row) % len(row_colors)]
                for c in col_indices:
                    cell = cells.get((r, c))
                    if cell is not None:
                        cell.set_facecolor(color)
                        cell.set_text_props(size=font_size)

            # Optional: highlight last row
            last_row_color = table_props.get("last_row_color")
            last_row_text_color = table_props.get("last_row_text_color")
            if last_row_color and last_row > header_row:
                for c in col_indices:
                    cell = cells.get((last_row, c))
                    if cell is not None:
                        cell.set_facecolor(last_row_color)
                        if last_row_text_color:
                            cell.set_text_props(
                                color=last_row_text_color, size=font_size
                            )

            # Column widths
            col_widths = table_props.get("column_widths")
            if isinstance(col_widths, list) and col_widths:
                for i, width in enumerate(col_widths):
                    for r in row_indices:
                        cell = cells.get((r, i))
                        if cell is not None:
                            cell.set_width(width)

            # General props
            table.auto_set_font_size(False)
            table.set_fontsize(font_size)
            table.scale(1, table_props.get("row_height", 2))
        except Exception:
            return


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
            # Use xlabel from the plot config, fallback to "Time" if not specified
            xlabel = plots_to_use[i - 1].get("xlabel", "Time")
            fig.update_xaxes(
                title_text=clean_axis_label(xlabel),
                row=i,
                col=1,
                showgrid=True,
                gridwidth=1,
                gridcolor="lightgray",
                zeroline=False,
                showline=True,
                linewidth=1,
                linecolor="black",
                showticklabels=True,
                tickmode="auto",
                nticks=10,
                tickformat=".1f",
                tickangle=0,
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
                showticklabels=True,
                tickmode="auto",
                nticks=8,
                tickformat=".2f",
            )

        # Synchronize all x-axes (time axis) for zooming and panning
        # This ensures that when you zoom/pan on one plot, all others follow
        fig.update_xaxes(matches="x")

        # Don't synchronize y-axes - each plot keeps its own scale
        # This allows each plot to have its own y-axis range

        return fig

    def _prepare_table_data(self, table_plot):
        """Prepare table data for a table plot"""
        headers = None
        data: list[list[str]] = []

        # Loop rows first (if any)
        if "loop_data" in table_plot:
            loop_config = table_plot["loop_data"]
            loop_headers = loop_config.get("headers", ["Description", "Value", "Unit"])
            headers = headers or loop_headers

            loop_var = loop_config.get("loop_var", [])
            if not loop_var:
                data.append(["No loop data specified", "", ""])  # placeholder row
            else:
                rows = []
                for item in loop_var:
                    row_data = []
                    for col_template in loop_config.get("columns", []):
                        if isinstance(col_template, dict):
                            if "template" in col_template:
                                template = col_template["template"]
                                processed_value = (
                                    template.replace("{{item}}", str(item))
                                    .replace("{item}", str(item))
                                    .replace("{value}", str(item))
                                )

                                if "var_template" in col_template:
                                    var_template = col_template["var_template"]
                                    var_name = var_template.replace(
                                        "{{item}}", str(item)
                                    ).replace("{item}", str(item))
                                    if (
                                        self._plots_data
                                        and var_name in self._plots_data[0]["data"]
                                        and len(self._plots_data[0]["data"][var_name])
                                        > 0
                                    ):
                                        value = self._plots_data[0]["data"][var_name][
                                            -1
                                        ]

                                        if "unit" in col_template:
                                            temp_data = {var_name: [value]}
                                            temp_data = convert_units(
                                                temp_data,
                                                [var_name],
                                                col_template["unit"],
                                            )
                                            value = temp_data[var_name][0]

                                        round_digits = col_template.get("round", 2)
                                        use_scientific = col_template.get(
                                            "use_scientific", False
                                        )
                                        scientific_threshold = col_template.get(
                                            "scientific_threshold", 1e6
                                        )
                                        value = format_number(
                                            value,
                                            round_digits,
                                            use_scientific,
                                            scientific_threshold,
                                        )

                                        prefix = col_template.get("prefix", "")
                                        suffix = col_template.get("suffix", "")
                                        value = f"{prefix}{value}{suffix}"

                                        processed_value = processed_value.replace(
                                            "{{value}}", str(value)
                                        ).replace("{value}", str(value))
                                    else:
                                        processed_value = processed_value.replace(
                                            "{{value}}",
                                            col_template.get("default", "N/A"),
                                        ).replace(
                                            "{value}",
                                            col_template.get("default", "N/A"),
                                        )

                                row_data.append(processed_value)
                            else:
                                row_data.append(col_template.get("value", ""))
                        else:
                            row_data.append(str(col_template))
                    rows.append(row_data)
                data.extend(rows)

        # Manual rows next (if any)
        if "manual_data" in table_plot:
            manual_data = table_plot["manual_data"]
            manual_headers = manual_data.get(
                "headers", ["Description", "Value", "Unit"]
            )
            headers = headers or manual_headers

            # Process manual rows
            rows = []
            for row in manual_data.get("rows", []):
                row_data = []
                for col in row:
                    if isinstance(col, dict):
                        # Handle dynamic values from data
                        if "var" in col:
                            var_name = col["var"]
                            # Use the first plot's data as reference
                            if (
                                self._plots_data
                                and var_name in self._plots_data[0]["data"]
                                and len(self._plots_data[0]["data"][var_name]) > 0
                            ):
                                value = self._plots_data[0]["data"][var_name][
                                    -1
                                ]  # Get last value

                                # Apply unit conversion if specified
                                if "unit" in col:
                                    temp_data = {var_name: [value]}
                                    temp_data = convert_units(
                                        temp_data, [var_name], col["unit"]
                                    )
                                    value = temp_data[var_name][0]

                                # Apply rounding if specified
                                round_digits = col.get("round", 2)
                                use_scientific = col.get("use_scientific", False)
                                scientific_threshold = col.get(
                                    "scientific_threshold", 1e6
                                )
                                value = format_number(
                                    value,
                                    round_digits,
                                    use_scientific,
                                    scientific_threshold,
                                )

                                # Add prefix/suffix if specified
                                prefix = col.get("prefix", "")
                                suffix = col.get("suffix", "")
                                value = f"{prefix}{value}{suffix}"

                                row_data.append(value)
                            else:
                                row_data.append(col.get("default", "N/A"))
                        else:
                            row_data.append(col.get("value", ""))
                    else:
                        row_data.append(str(col))
                rows.append(row_data)
            data.extend(rows)

        # Fallbacks
        if headers is None:
            headers = ["Description", "Value", "Unit"]
        if not data:
            data = [["No data available", "", ""]]

        return {"headers": headers, "data": data}

    def _add_textfield_multi_plot(self, fig, textfield_config, row, data):
        """Add a single textfield annotation to a specific subplot in the multi-plot"""
        prefix = textfield_config.get("prefix", "")
        var = textfield_config.get("var", "time")
        round_digits = textfield_config.get("round", 2)
        suffix = textfield_config.get("suffix", "")

        # Obtain last value safely, with optional unit conversion on a temp value
        if var in data and len(data[var]) > 0:
            value = data[var][-1]
            if "unit" in textfield_config:
                temp_data = {var: [value]}
                temp_data = convert_units(temp_data, [var], textfield_config["unit"])
                value = temp_data[var][0]
        else:
            value = textfield_config.get("default", "N/A")

        # Format number if possible, else use string representation
        try:
            numeric_value = float(value)
            use_scientific = textfield_config.get("use_scientific", False)
            scientific_threshold = textfield_config.get("scientific_threshold", 1e6)
            formatted_value = format_number(
                numeric_value, round_digits, use_scientific, scientific_threshold
            )
        except (TypeError, ValueError):
            formatted_value = str(value)

        text = f"{prefix}{formatted_value}{suffix}"
        x = textfield_config.get("x", 0.05)
        y = textfield_config.get("y", 0.95)
        fontsize = textfield_config.get("fontsize", 10)

        # Add annotation to the specific subplot relative to its domain
        axis_suffix = "" if row == 1 else str(row)
        xref = f"x{axis_suffix} domain"
        yref = f"y{axis_suffix} domain"
        fig.add_annotation(
            x=x,
            y=y,
            xref=xref,
            yref=yref,
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
        "table": TablePlot,
        "plotly_table": PlotlyTablePlot,
    }

    @staticmethod
    def instantiate_plot(plot_type, data, config):
        if plot_type in PlotFactory.plot_types:
            return PlotFactory.plot_types[plot_type](data, config)
        else:
            raise NotImplementedError(f"Plot type {plot_type} not implemented")
