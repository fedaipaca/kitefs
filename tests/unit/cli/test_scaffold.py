"""Unit tests for kitefs.cli.scaffold — pure scaffold logic, no CLI invocation."""

from __future__ import annotations

import pytest
import yaml

from kitefs.cli import scaffold
from kitefs.errors import ConfigurationError


class TestInitProducerTree:
    """init_producer creates the expected file and directory tree."""

    def test_creates_all_expected_paths(self, tmp_path) -> None:
        """All documented producer paths are created."""
        scaffold.init_producer(tmp_path)

        assert (tmp_path / "kitefs.yaml").is_file()
        assert (tmp_path / "feature_store" / "definitions" / "town_market_features.py").is_file()
        assert (tmp_path / "feature_store" / "registry.json").is_file()
        assert (tmp_path / "feature_store" / "data" / "offline_store").is_dir()
        assert (tmp_path / "feature_store" / "data" / "online_store").is_dir()
        assert (tmp_path / ".gitignore").is_file()

    def test_does_not_create_online_db(self, tmp_path) -> None:
        """online.db is not created — it's lazy per docs/05."""
        scaffold.init_producer(tmp_path)
        assert not (tmp_path / "feature_store" / "data" / "online_store" / "online.db").exists()


class TestInitProducerFileContents:
    """init_producer writes the correct content to each generated file."""

    def test_kitefs_yaml_byte_identical_to_template(self, tmp_path) -> None:
        """Generated kitefs.yaml is byte-identical to PRODUCER_CONFIG_TEMPLATE."""
        scaffold.init_producer(tmp_path)
        content = (tmp_path / "kitefs.yaml").read_text(encoding="utf-8")
        assert content == scaffold.PRODUCER_CONFIG_TEMPLATE

    def test_kitefs_yaml_parses_as_valid_yaml(self, tmp_path) -> None:
        """kitefs.yaml is valid YAML with the hardcoded MVP project name."""
        scaffold.init_producer(tmp_path)
        data = yaml.safe_load((tmp_path / "kitefs.yaml").read_text(encoding="utf-8"))
        assert data["project"]["name"] == "kitefs_featurestore_project"
        assert data["version"] == 1

    def test_kitefs_yaml_includes_remote_sections(self, tmp_path) -> None:
        """Generated kitefs.yaml includes registry, offline_store, and online_store."""
        scaffold.init_producer(tmp_path)
        data = yaml.safe_load((tmp_path / "kitefs.yaml").read_text(encoding="utf-8"))
        assert "registry" in data["remote"]
        assert "offline_store" in data["remote"]
        assert "online_store" in data["remote"]

    def test_registry_json_exact_bytes(self, tmp_path) -> None:
        """registry.json matches the canonical empty-registry serialization."""
        scaffold.init_producer(tmp_path)
        content = (tmp_path / "feature_store" / "registry.json").read_text(encoding="utf-8")
        assert content == scaffold.EMPTY_REGISTRY
        assert content == '{\n  "feature_groups": {}\n}\n'

    def test_example_definition_byte_identical_to_constant(self, tmp_path) -> None:
        """town_market_features.py content matches the EXAMPLE_DEFINITION constant."""
        scaffold.init_producer(tmp_path)
        content = (tmp_path / "feature_store" / "definitions" / "town_market_features.py").read_text(encoding="utf-8")
        assert content == scaffold.EXAMPLE_DEFINITION

    def test_example_definition_has_leading_comment_and_trailing_newline(self) -> None:
        """EXAMPLE_DEFINITION starts with the file-path comment and ends with a newline."""
        assert scaffold.EXAMPLE_DEFINITION.startswith("# feature_store/definitions/town_market_features.py")
        assert "town_market_features = FeatureGroup(" in scaffold.EXAMPLE_DEFINITION
        assert scaffold.EXAMPLE_DEFINITION.endswith("\n")


class TestInitProducerGitignore:
    """init_producer manages .gitignore entries correctly for all four sub-cases."""

    @pytest.mark.parametrize(
        ("pre_existing", "expected_content_after"),
        [
            pytest.param(
                None,
                "feature_store/data/\nfeature_store/registry.json\n",
                id="absent",
            ),
            pytest.param(
                "# existing comment\n",
                "# existing comment\nfeature_store/data/\nfeature_store/registry.json\n",
                id="present_without_entries",
            ),
            pytest.param(
                "feature_store/data/\n",
                "feature_store/data/\nfeature_store/registry.json\n",
                id="present_with_first_entry",
            ),
            pytest.param(
                "feature_store/data/\nfeature_store/registry.json\n",
                "feature_store/data/\nfeature_store/registry.json\n",
                id="present_with_both_entries",
            ),
        ],
    )
    def test_gitignore_content_after_init(
        self, tmp_path, pre_existing: str | None, expected_content_after: str
    ) -> None:
        """After init_producer, .gitignore contains the expected content."""
        gi_path = tmp_path / ".gitignore"
        if pre_existing is not None:
            gi_path.write_text(pre_existing, encoding="utf-8")

        scaffold.init_producer(tmp_path)

        assert gi_path.read_text(encoding="utf-8") == expected_content_after

    def test_gitignore_does_not_ignore_definitions_dir(self, tmp_path) -> None:
        """feature_store/definitions/ is not listed in .gitignore."""
        scaffold.init_producer(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "feature_store/definitions" not in content

    def test_original_gitignore_bytes_preserved_when_appending(self, tmp_path) -> None:
        """Appending to an existing .gitignore leaves original bytes unchanged."""
        original = "# comment without trailing newline"
        (tmp_path / ".gitignore").write_text(original, encoding="utf-8")

        scaffold.init_producer(tmp_path)

        result = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert result.startswith(original)


class TestInitProducerGuards:
    """init_producer raises ConfigurationError on conflicting pre-existing files."""

    def test_raises_when_kitefs_yaml_exists(self, tmp_path) -> None:
        """ConfigurationError raised when kitefs.yaml already exists; nothing written."""
        (tmp_path / "kitefs.yaml").write_text("existing", encoding="utf-8")

        with pytest.raises(ConfigurationError) as exc_info:
            scaffold.init_producer(tmp_path)

        assert "kitefs.yaml already exists" in str(exc_info.value)
        assert str(tmp_path.resolve() / "kitefs.yaml") in str(exc_info.value)
        # Nothing else was created
        assert not (tmp_path / "feature_store").exists()

    def test_raises_when_registry_json_exists(self, tmp_path) -> None:
        """ConfigurationError raised when registry.json already exists."""
        registry_path = tmp_path / "feature_store" / "registry.json"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text("{}", encoding="utf-8")

        with pytest.raises(ConfigurationError) as exc_info:
            scaffold.init_producer(tmp_path)

        assert str(registry_path.resolve()) in str(exc_info.value)
        assert not (tmp_path / "kitefs.yaml").exists()

    def test_raises_when_definition_file_exists(self, tmp_path) -> None:
        """ConfigurationError raised when town_market_features.py already exists."""
        def_path = tmp_path / "feature_store" / "definitions" / "town_market_features.py"
        def_path.parent.mkdir(parents=True)
        def_path.write_text("# existing", encoding="utf-8")

        with pytest.raises(ConfigurationError) as exc_info:
            scaffold.init_producer(tmp_path)

        assert str(def_path.resolve()) in str(exc_info.value)
        assert not (tmp_path / "kitefs.yaml").exists()


class TestInitProducerRollback:
    """On failure partway through, init_producer removes only the files it created."""

    def test_rollback_removes_created_files_on_registry_write_failure(self, tmp_path, monkeypatch) -> None:
        """When registry.json write fails, the definition file is removed (rollback)."""
        original_write = scaffold._atomic_write_text

        def fail_on_registry(path, content, created):
            if path.name == "registry.json":
                raise OSError("simulated disk full")
            original_write(path, content, created)

        monkeypatch.setattr(scaffold, "_atomic_write_text", fail_on_registry)

        with pytest.raises(OSError):
            scaffold.init_producer(tmp_path)

        assert not (tmp_path / "feature_store" / "definitions" / "town_market_features.py").exists()
        assert not (tmp_path / "feature_store" / "registry.json").exists()
        assert not (tmp_path / "kitefs.yaml").exists()
        # Directories created before the failure remain (per spec).
        assert (tmp_path / "feature_store").is_dir()

    def test_rollback_removes_created_files_on_config_write_failure(self, tmp_path, monkeypatch) -> None:
        """When kitefs.yaml write fails, all previously created files are removed."""
        original_write = scaffold._atomic_write_text

        def fail_on_config(path, content, created):
            if path.name == "kitefs.yaml":
                raise OSError("simulated disk full")
            original_write(path, content, created)

        monkeypatch.setattr(scaffold, "_atomic_write_text", fail_on_config)

        with pytest.raises(OSError):
            scaffold.init_producer(tmp_path)

        assert not (tmp_path / "kitefs.yaml").exists()
        assert not (tmp_path / "feature_store" / "registry.json").exists()
        assert not (tmp_path / "feature_store" / "definitions" / "town_market_features.py").exists()
        assert not (tmp_path / ".gitignore").exists()
        # Directories remain (not tracked for rollback).
        assert (tmp_path / "feature_store").is_dir()


class TestInitProducerSummary:
    """init_producer returns the correct stdout summary string."""

    def test_summary_format_new_gitignore(self, tmp_path) -> None:
        """Summary includes .gitignore line when .gitignore is created fresh."""
        summary = scaffold.init_producer(tmp_path)
        lines = summary.split("\n")
        assert lines[0] == f"Created KiteFS producer scaffold in {tmp_path.resolve()}:"
        assert "  kitefs.yaml" in lines
        assert "  feature_store/definitions/town_market_features.py" in lines
        assert "  feature_store/registry.json" in lines
        assert "  feature_store/data/offline_store/" in lines
        assert "  feature_store/data/online_store/" in lines
        assert "  .gitignore" in lines
        assert any("kitefs apply" in line for line in lines)

    def test_summary_gitignore_appended_variant(self, tmp_path) -> None:
        """Summary shows 'appended N entry/entries' when .gitignore is pre-existing."""
        (tmp_path / ".gitignore").write_text("# existing\n", encoding="utf-8")
        summary = scaffold.init_producer(tmp_path)
        assert "  .gitignore (appended 2 entries)" in summary

    def test_summary_gitignore_omitted_when_untouched(self, tmp_path) -> None:
        """Summary omits .gitignore line when both entries already present."""
        (tmp_path / ".gitignore").write_text("feature_store/data/\nfeature_store/registry.json\n", encoding="utf-8")
        summary = scaffold.init_producer(tmp_path)
        assert ".gitignore" not in summary

    def test_summary_appended_singular_entry(self, tmp_path) -> None:
        """Summary uses singular 'entry' when exactly one entry is appended."""
        (tmp_path / ".gitignore").write_text("feature_store/data/\n", encoding="utf-8")
        summary = scaffold.init_producer(tmp_path)
        assert "  .gitignore (appended 1 entry)" in summary


class TestInitConfig:
    """init_config creates only kitefs.yaml with the consumer template."""

    def test_creates_only_kitefs_yaml(self, tmp_path) -> None:
        """Only kitefs.yaml is created; no feature_store/ dir or .gitignore."""
        scaffold.init_config(tmp_path)

        assert (tmp_path / "kitefs.yaml").is_file()
        assert not (tmp_path / "feature_store").exists()
        assert not (tmp_path / ".gitignore").exists()

    def test_kitefs_yaml_byte_identical_to_consumer_template(self, tmp_path) -> None:
        """Generated kitefs.yaml is byte-identical to CONSUMER_CONFIG_TEMPLATE."""
        scaffold.init_config(tmp_path)
        content = (tmp_path / "kitefs.yaml").read_text(encoding="utf-8")
        assert content == scaffold.CONSUMER_CONFIG_TEMPLATE

    def test_consumer_yaml_has_no_offline_store(self, tmp_path) -> None:
        """Consumer kitefs.yaml omits remote.offline_store."""
        scaffold.init_config(tmp_path)
        data = yaml.safe_load((tmp_path / "kitefs.yaml").read_text(encoding="utf-8"))
        assert "offline_store" not in data["remote"]

    def test_consumer_yaml_includes_registry_and_online_store(self, tmp_path) -> None:
        """Consumer kitefs.yaml includes remote.registry and remote.online_store."""
        scaffold.init_config(tmp_path)
        data = yaml.safe_load((tmp_path / "kitefs.yaml").read_text(encoding="utf-8"))
        assert "registry" in data["remote"]
        assert "online_store" in data["remote"]

    def test_consumer_runtime_target_defaults_to_remote(self, tmp_path) -> None:
        """Consumer kitefs.yaml has runtime.target defaulting to remote."""
        scaffold.init_config(tmp_path)
        content = (tmp_path / "kitefs.yaml").read_text(encoding="utf-8")
        assert "${KITEFS_RUNTIME_TARGET:-remote}" in content

    def test_raises_when_kitefs_yaml_exists(self, tmp_path) -> None:
        """ConfigurationError raised when kitefs.yaml already exists; nothing else created."""
        (tmp_path / "kitefs.yaml").write_text("existing", encoding="utf-8")

        with pytest.raises(ConfigurationError) as exc_info:
            scaffold.init_config(tmp_path)

        assert "kitefs.yaml already exists" in str(exc_info.value)
        assert "kitefs init-config" in str(exc_info.value)
        # Original file unchanged.
        assert (tmp_path / "kitefs.yaml").read_text(encoding="utf-8") == "existing"

    def test_summary_names_config_and_next_step(self, tmp_path) -> None:
        """Summary names kitefs.yaml and mentions placeholder edit next step."""
        summary = scaffold.init_config(tmp_path)
        assert "kitefs.yaml" in summary
        assert "bucket" in summary or "dynamodb_table_prefix" in summary
