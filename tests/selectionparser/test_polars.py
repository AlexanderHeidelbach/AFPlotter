import json

import polars as pl
import pytest

from afplotter.selectionparser.polars import SelectionOperator, SelectionParser, read_json


@pytest.fixture
def sample_lazyframe():
    return pl.LazyFrame({"pt": [1.0, 5.0, 10.0], "eta": [0.1, -0.5, 2.5], "flag": [True, False, True]})


class TestSelectionParser:
    def test_simple_comparison(self, sample_lazyframe):
        expr = SelectionParser("pt > 3").parse()
        result = sample_lazyframe.filter(expr).collect()
        assert result["pt"].to_list() == [5.0, 10.0]

    def test_and_combination(self, sample_lazyframe):
        expr = SelectionParser("pt > 3 and eta < 1").parse()
        result = sample_lazyframe.filter(expr).collect()
        assert result["pt"].to_list() == [5.0]

    def test_or_combination(self, sample_lazyframe):
        expr = SelectionParser("pt < 2 or pt > 8").parse()
        result = sample_lazyframe.filter(expr).collect()
        assert result["pt"].to_list() == [1.0, 10.0]

    def test_bitwise_and_or(self, sample_lazyframe):
        expr = SelectionParser("(pt > 3) & (eta < 1)").parse()
        result = sample_lazyframe.filter(expr).collect()
        assert result["pt"].to_list() == [5.0]

    def test_unary_minus(self, sample_lazyframe):
        expr = SelectionParser("eta > -1").parse()
        result = sample_lazyframe.filter(expr).collect()
        assert result["eta"].to_list() == [0.1, -0.5, 2.5]

    def test_invalid_syntax_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to parse selection query"):
            SelectionParser("pt >> 3 ???").parse()

    def test_non_string_input_raises_type_error(self):
        with pytest.raises(TypeError, match="Input must be a string"):
            SelectionParser(123)  # type: ignore[arg-type]


class TestSelectionOperator:
    def test_apply_inline_selections(self, sample_lazyframe):
        op = SelectionOperator(sample_lazyframe, selections={"cut1": "pt > 3"})
        result = op.apply_selections().collect()
        assert result["pt"].to_list() == [5.0, 10.0]

    def test_apply_selections_from_explicit_path(self, sample_lazyframe, tmp_path):
        selections_file = tmp_path / "cuts.json"
        selections_file.write_text(json.dumps({"cut1": "pt > 3"}))
        op = SelectionOperator(sample_lazyframe, selections_path=selections_file)
        result = op.apply_selections().collect()
        assert result["pt"].to_list() == [5.0, 10.0]

    def test_requires_selections_or_path(self, sample_lazyframe):
        with pytest.raises(ValueError, match="Either selections_path or selections must be provided"):
            SelectionOperator(sample_lazyframe)

    def test_missing_column_raises_value_error(self, sample_lazyframe):
        op = SelectionOperator(sample_lazyframe, selections={"cut1": "nonexistent > 3"})
        with pytest.raises(ValueError, match="do not exist in the LazyFrame"):
            op.apply_selections()


def test_read_json(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"a": 1}))
    assert read_json(path) == {"a": 1}
