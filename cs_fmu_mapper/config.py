import logging
import os
import pathlib
from pathlib import Path
from typing import IO, Any, Literal, Union

import jinja2
from jinja2 import Environment, FileSystemLoader
from omegaconf import DictConfig, ListConfig, ListMergeMode, OmegaConf
from omegaconf.errors import OmegaConfBaseException


class Config:
    """
    Configuration class for the cs-fmu-mapper.

    This class is responsible for loading and processing configuration files.
    It supports both full configurations and component-specific configurations.
    """

    def __init__(
        self,
        config_file_path: Union[str, Path],
        config_dir: Union[str, Path] = os.path.join(
            Path(__file__).parent.parent, "example", "configs"
        ),
    ):
        self._config_dir = config_dir
        self._env = Environment(loader=FileSystemLoader(self._config_dir))
        self._config = OmegaConf.create()
        self._settings_config = self._load_partial_settings(
            Path(self._config_dir) / config_file_path
        )
        try:
            self._modular_config = self._settings_config.modular_config
        except AttributeError:
            self._modular_config = False
        if self._modular_config:
            self._handle_modular_config(config_file_path)
        else:
            self._handle_full_config()
        if "modular_config" in self._config:
            del self._config["modular_config"]

    def _handle_full_config(self):
        print(
            "No Components found in the config file. Assuming the provided config is a full config."
        )
        self._config = self._settings_config

    def _handle_modular_config(self, config_file_path: Union[str, Path]):
        for component, config_names in self._settings_config.Components.items():
            self._load_component_configs(component, config_names)
        self._merge_config(Path(config_file_path))
        self._generate_mappings()

    def _load_component_configs(
        self, component: str, config_names: Union[str, ListConfig]
    ):
        if isinstance(config_names, ListConfig):
            for config_name in config_names:
                self._merge_config(f"{component}/{config_name}.yaml")
        else:
            self._merge_config(f"{component}/{config_names}.yaml")

    def remove_prefix(self, var: str, index: int = 2) -> str:
        """
        Remove the prefix from a variable name.

        This method assumes that the variable name has at least two parts
        separated by dots, and removes the first two parts.

        Args:
            var (str): The variable name with a prefix.
            index (int): The index of the last part to remove. Defaults to 2.

        Returns:
            str: The variable name without the prefix.

        Example:
            >>> self.remove_prefix("model.out.temperature")
            "temperature"
        """
        parts = var.split(".")
        return ".".join(parts[index:]) if len(parts) > index else var

    def transform_vars(
        self, vars: dict[str, Any], prefix: str, direction: Literal["in", "out"]
    ) -> dict[str, Any]:
        """
        Transform variable names in a dictionary by changing their prefix.

        This method takes a dictionary of variables, a new prefix, and a direction
        ("in" or "out"), and returns a new dictionary with transformed variable names.

        Args:
            vars (dict[str, Any]): The input dictionary of variables.
            prefix (str): The new prefix to be added to the variable names.
            direction (Literal["in", "out"]): The direction to be added after the prefix.

        Returns:
            dict[str, Any]: A new dictionary with transformed variable names.

        Example:
            >>> self.transform_vars({"model.out.temp": 25}, "algo", "in")
            {"algo.in.temp": 25}
        """
        return {
            f"{prefix}.{direction}.{self.remove_prefix(k)}": v for k, v in vars.items()
        }

    def _assert_mapping_rule(self, rule: dict, prefix_rules: dict) -> None:
        """
        Assert that a mapping rule is valid.

        Args:
            rule (dict): The mapping rule to validate.
            prefix_rules (dict): The prefix rules for components.

        Raises:
            AssertionError: If the rule is invalid.
        """
        if "source" in rule:
            assert (
                isinstance(rule["source"], dict) and len(rule["source"]) == 1
            ), "Source must be a dict with one key-value pair"
            source_component, source_var_type = next(iter(rule["source"].items()))
            assert (
                source_component in prefix_rules
            ), f"Source component '{source_component}' must be in Prefix"
            assert source_var_type in [
                "outputVar",
                "inputVar",
            ], f"Source var_type must be 'outputVar' or 'inputVar', got '{source_var_type}'"

        assert "destination" in rule, "Rule must have a 'destination' key"
        assert (
            isinstance(rule["destination"], dict) and len(rule["destination"]) == 1
        ), "Destination must be a dict with one key-value pair"

        dest_component, dest_var_type = next(iter(rule["destination"].items()))
        assert (
            dest_component in prefix_rules
        ), f"Destination component '{dest_component}' must be in Prefix"
        assert dest_var_type in [
            "outputVar",
            "inputVar",
        ], f"Destination var_type must be 'outputVar' or 'inputVar', got '{dest_var_type}'"

    def _generate_mappings(self) -> None:
        """
        Generate a mapping of preStepMappings and postStepMappings from the configuration.

        This method processes the MappingRules defined in the configuration to create
        a mapping structure. It handles both preStepMappings and postStepMappings,
        which define how variables should be mapped between different components.

        The method performs the following steps:
        1. Extracts mapping rules and prefix rules from the configuration.
        2. Iterates through each component and its rules in the mapping rules.
        3. Validates that components and variable types exist in the configuration.
        4. Processes each rule to create source and destination keys.
        5. Adds valid mappings to the mapper structure.

        The method also includes several safety checks:
        - It ignores components that are in MappingRules but not in the main configuration.
        - It skips variable types that are not found in a component's configuration.
        - It ignores rules where either the source or destination component is not in the configuration.

        The resulting mapper is merged into the configuration under the "Mapping" key.

        Note:
        - This method modifies the internal _config attribute.
        - It logs informational messages when ignoring rules due to missing components or variable types.

        Raises:
        - Any exceptions raised during the OmegaConf merge operation.
        - KeyError if MappingRules, Components, or Prefix are not found in the configuration.
        """
        mapper = OmegaConf.create({"preStepMappings": {}, "postStepMappings": {}})

        if "MappingRules" not in self._config:
            raise KeyError("MappingRules not found in the configuration")
        if "Components" not in self._config.MappingRules:
            raise KeyError("Components not found in MappingRules")
        if "Prefix" not in self._config.MappingRules:
            raise KeyError("Prefix not found in MappingRules")
        assert isinstance(self._config, DictConfig), "Config must be a DictConfig"

        mapping_rules: dict[str, dict[str, list]] = OmegaConf.to_container(
            self._config.MappingRules.Components
        )  # type: ignore
        prefix_rules: dict[str, str] = OmegaConf.to_container(
            self._config.MappingRules.Prefix
        )  # type: ignore

        for component, rules in mapping_rules.items():
            if component not in self._config:
                logging.info(
                    f"Component '{component}' found in MappingRules but not in config. Ignoring its rules."
                )
                continue

            for var_type, var_rules in rules.items():
                if var_type not in self._config[component]:
                    logging.info(
                        f"Variable type '{var_type}' not found in component '{component}'. Ignoring its rules."
                    )
                    continue

                for rule in var_rules:
                    self._assert_mapping_rule(rule, prefix_rules)

                    source = rule.get("source", {component: var_type})
                    source_component, source_var_type = next(iter(source.items()))

                    dest_component, dest_var_type = next(
                        iter(rule["destination"].items())
                    )

                    if (
                        source_component not in self._config
                        or dest_component not in self._config
                    ):
                        logging.info(
                            f"Source component '{source_component}' or destination component '{dest_component}' not found in config. Ignoring this rule."
                        )
                        continue

                    mapping_type = rule.get("type", "postStepMappings")

                    source_prefix = prefix_rules[source_component]
                    dest_prefix = prefix_rules[dest_component]

                    source_direction = "out" if source_var_type == "outputVar" else "in"
                    dest_direction = "in" if dest_var_type == "inputVar" else "out"

                    for var in self._config[component][var_type].keys():
                        var = self.remove_prefix(var)
                        source_key = f"{source_prefix}.{source_direction}.{var}"
                        dest_key = f"{dest_prefix}.{dest_direction}.{var}"

                        if (
                            source_key
                            in self._config[source_component][source_var_type]
                            and dest_key in self._config[dest_component][dest_var_type]
                        ):
                            mapper[mapping_type].setdefault(source_key, [])
                            mapper[mapping_type][source_key].append(dest_key)

        self._config = OmegaConf.merge(
            self._config,
            {"Mapping": mapper},
            list_merge_mode=ListMergeMode.EXTEND_UNIQUE,
        )

    def _merge_config(self, config_path: Union[str, pathlib.Path, IO[Any]]) -> None:
        """
        Load a configuration file and merge it with the current combined configuration.

        This method loads a configuration file using the _load_config method,
        then merges it with the existing configuration using OmegaConf.merge.
        The merge is performed with EXTEND_UNIQUE list merge mode to avoid duplicates.

        Args:
            config_path (Union[str, pathlib.Path, IO[Any]]): Path to the configuration
                file or a file-like object containing the configuration.

        Raises:
            ValueError: If there's an error loading or merging the configuration.
        """
        try:
            component_config = self._load_config(str(config_path))
            self._config = OmegaConf.merge(
                self._config,
                component_config,
                list_merge_mode=ListMergeMode.EXTEND_UNIQUE,
            )
        except (FileNotFoundError, ValueError, OmegaConfBaseException) as e:
            raise ValueError(
                f"Error merging configuration from {config_path}: {str(e)}"
            )

    def _load_config(
        self, config_path: Union[str, pathlib.Path, IO[Any]]
    ) -> DictConfig | ListConfig:
        """
        Load and process a YAML configuration file with Jinja2 templating.

        This method loads a YAML file, renders any Jinja2 templates within it
        using the current combined configuration as context, and then creates
        an OmegaConf configuration object from the rendered YAML.

        Args:
            config_path (Union[str, pathlib.Path, IO[Any]]): Path to the YAML
                configuration file or a file-like object containing the configuration.

        Returns:
            DictConfig | ListConfig: An OmegaConf configuration object created
            from the rendered YAML.

        Raises:
            jinja2.TemplateNotFound: If the template file cannot be found.
            jinja2.TemplateError: If there's an error in the Jinja2 template.
            OmegaConfBaseException: If there's an error creating the OmegaConf object.
        """
        try:
            template = self._env.get_template(str(config_path))
            context = {**self._config, "transform_vars": self.transform_vars}  # type: ignore
            rendered_yaml = template.render(**context)
            return OmegaConf.create(rendered_yaml)
        except jinja2.TemplateNotFound:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except jinja2.TemplateError as e:
            raise ValueError(f"Error in Jinja2 template: {e}")
        except OmegaConfBaseException as e:
            raise ValueError(f"Error creating OmegaConf object: {e}")

    def _load_partial_settings(
        self, settings_path: Union[str, pathlib.Path]
    ) -> DictConfig | ListConfig:
        """
        Load the initial part of a YAML configuration file.

        This method reads the file up to a specific comment line, which separates
        the component definitions from the rest of the configuration. This approach
        allows for loading component information before processing Jinja2 templates
        that may depend on these components.

        Args:
            settings_path (Union[str, pathlib.Path]): Path to the settings YAML file.

        Returns:
            DictConfig | ListConfig: Parsed configuration up to the separator comment.

        Note:
            The file should contain a line with the comment '# END_COMPONENT_DEFINITIONS'
            after all component definitions. This line acts as a separator.
        """
        separator_comment = "# END_COMPONENT_DEFINITIONS"

        with open(settings_path, "r") as file:
            partial_yaml_content = []
            for line in file:
                if separator_comment in line:
                    break
                partial_yaml_content.append(line)

        partial_yaml_str = "".join(partial_yaml_content)
        return OmegaConf.create(partial_yaml_str)

    def _remove_settings_config(self):
        """Remove self._settings_config from self._config."""
        for key in self._settings_config.keys():
            if key in self._config:
                del self._config[key]  # type: ignore

    def get_config(self) -> dict[str, Any]:
        """Returns the combined config from the settings and the Components."""
        return OmegaConf.to_container(self._config)  # type: ignore


if __name__ == "__main__":
    config = Config(config_file_path="modular_config.yaml")
    print(config.get_config())
    OmegaConf.save(config.get_config(), str(config._config_dir) + "/output.yaml")
