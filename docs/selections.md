# Selections

`SelectionParser` turns a query string into a Polars filter expression:

```python
from afplotter import SelectionParser
expr = SelectionParser("pt > 5 and eta > -2 and eta < 2").parse()
```

Supports `and`/`or`, `&`/`|`, comparisons (`>`, `>=`, `<`, `<=`, `==`, `!=`),
`is`/`is not`, and unary `-`/`+`. Function calls (`abs(eta) < 2`) raise a
`ValueError`. Chained comparisons (`-2 < eta < 2`) are supported and AND
together each pairwise comparison, equivalent to `eta > -2 and eta < 2`.

`is`/`is not` are for null and NaN checks: `x is None` maps to
`x.is_null()`, `x is not None` maps to `x.is_not_null()`, `x is NaN` maps to
`x.is_nan()`, and `x is not NaN` maps to `~x.is_nan()`. Like every other
comparison in this parser, NaN-ness is null-propagating — `x is not NaN`
excludes null rows too, since a null value is neither NaN nor "not NaN" but
unknown. Use `x is None`/`x is not None` if you specifically want to
include or exclude the null rows.

`SelectionOperator` applies one or more named selections to a Polars
`LazyFrame`, either inline or from a JSON file:

```python
from afplotter import SelectionOperator

# inline
op = SelectionOperator(lazyframe, selections={"cut1": "pt > 5"})

# from a file: {"cut1": "pt > 5", "cut2": "eta > -2 and eta < 2"}
op = SelectionOperator(lazyframe, selections_path="configs/my_selection.json")

filtered = op.apply_selections()
```

Raises `ValueError` if a selection references a column that doesn't exist in
the LazyFrame.
