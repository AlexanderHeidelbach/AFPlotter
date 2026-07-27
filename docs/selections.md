# Selections

`SelectionParser` turns a query string into a Polars filter expression:

```python
from afplotter import SelectionParser
expr = SelectionParser("pt > 5 and eta > -2 and eta < 2").parse()
```

Supports `and`/`or`, `&`/`|`, comparisons (`>`, `>=`, `<`, `<=`, `==`, `!=`),
`is`, and unary `-`/`+`. Function calls (`abs(eta) < 2`) raise a
`ValueError`, and chained comparisons (`-2 < eta < 2`) silently evaluate to
the wrong filter rather than erroring — spell both out as separate
`and`-joined comparisons instead (`eta > -2 and eta < 2`).

`is` currently has two known issues: `x is NaN` correctly filters to
non-null rows, but `x is None` does the opposite (filters to non-null
rather than null rows), and `is not` always raises a `ValueError`. Until
these are fixed, prefer Polars' own `.is_null()`/`.is_not_null()` directly
on the LazyFrame for null-specific filtering rather than routing it through
a `SelectionParser` query string.

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
