import pytest

from kitefs import DefinitionError, Metadata


class TestMetadata:
    """Metadata construction-time validation of description and owner."""

    def test_valid_construction(self) -> None:
        """Metadata with non-empty description and owner constructs successfully."""
        m = Metadata(description="A description", owner="team-a")
        assert m.description == "A description"
        assert m.owner == "team-a"

    def test_tags_defaults_to_empty_dict(self) -> None:
        """tags defaults to {} when not provided."""
        m = Metadata(description="desc", owner="owner")
        assert m.tags == {}

    def test_tags_stored_when_provided(self) -> None:
        """tags is stored as provided."""
        m = Metadata(description="desc", owner="owner", tags={"env": "prod"})
        assert m.tags == {"env": "prod"}

    @pytest.mark.parametrize(
        "description",
        [
            pytest.param("", id="empty_string"),
            pytest.param("   ", id="whitespace_only"),
        ],
    )
    def test_rejects_empty_description(self, description: str) -> None:
        """Metadata raises DefinitionError when description is empty or whitespace."""
        with pytest.raises(DefinitionError):
            Metadata(description=description, owner="team-a")

    @pytest.mark.parametrize(
        "owner",
        [
            pytest.param("", id="empty_string"),
            pytest.param("   ", id="whitespace_only"),
        ],
    )
    def test_rejects_empty_owner(self, owner: str) -> None:
        """Metadata raises DefinitionError when owner is empty or whitespace."""
        with pytest.raises(DefinitionError) as exc_info:
            Metadata(description="A description", owner=owner)
        assert "owner" in str(exc_info.value)
