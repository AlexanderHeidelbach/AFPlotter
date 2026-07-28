import ast
from functools import reduce
import json
import operator
from pathlib import Path
from typing import Any

import polars as pl
from afplotter.baseplotter import PathType

def read_json(filename: PathType) -> dict[str, Any]:
    with open(filename, "r") as f:
        return json.load(f)

class SelectionParser:
    """
    Parses a query string into a Polars filter expression.
    Supports logical (and/or) and comparison operators.
    """

    OPS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.And: operator.and_,
        ast.Or: operator.or_,
        ast.Is: lambda a, b: a.is_nan() if b != b else a.is_null(),
        ast.IsNot: lambda a, b: ~a.is_nan() if b != b else a.is_not_null(),
    }

    def __init__(self, query_input: str):
        if not isinstance(query_input, str):
            raise TypeError("Input must be a string")
        self.expression = query_input

    def parse(self) -> pl.Expr:
        try:
            parsed_ast = ast.parse(self.expression, mode="eval").body
            return self._parse_expr(parsed_ast)
        except Exception as e:
            raise ValueError(f"Failed to parse selection query: {e}")

    def _parse_expr(self, node, in_lhs_of_comparison=False):
        if isinstance(node, ast.BoolOp):
            op_func = self.OPS[type(node.op)]
            return reduce(op_func, (self._parse_expr(v) for v in node.values))

        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
            return self._parse_expr(node.left) & self._parse_expr(node.right)

        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return self._parse_expr(node.left) | self._parse_expr(node.right)

        elif isinstance(node, ast.Compare):
            operands = [self._parse_expr(node.left, in_lhs_of_comparison=True)]
            operands.extend(self._parse_expr(comparator) for comparator in node.comparators)
            comparisons = (
                self.OPS[type(op)](operands[i], operands[i + 1])
                for i, op in enumerate(node.ops)
            )
            return reduce(operator.and_, comparisons)

        elif isinstance(node, ast.Name):
            if node.id == "NaN":
                return float("nan")
            return pl.col(node.id)

        elif isinstance(node, ast.Constant):
            if isinstance(node.value, str) and in_lhs_of_comparison:
                return pl.col(node.value)
            return node.value

        elif isinstance(node, ast.UnaryOp):
            operand = self._parse_expr(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.UAdd):
                return operand
            else:
                raise ValueError(f"Unsupported unary operator: {ast.dump(node.op)}")

        else:
            raise ValueError(f"Unsupported expression: {ast.dump(node)}")


class SelectionOperator:
    """
    Applies a query-string-based filter to a Polars LazyFrame.
    """

    def __init__(
        self,
        lazyframe: pl.LazyFrame,
        selections_path: str | Path | None = None,
        selections: dict[str, str] | None = None,
    ) -> None:
        self.lazyframe = lazyframe
        if selections_path is not None:
            self.selections = self._load_query_string(selections_path)
        elif selections is not None:
            self.selections = selections
        else:
            raise ValueError(
                "Either selections_path or selections must be provided."
            )

    def _load_query_string(self, selections_path: str | Path) -> dict[str, str]:
        """
        Loads the query string dict from a JSON file at the given path.
        """
        return read_json(selections_path)

    def _validate_columns(self, expr: pl.Expr) -> None:
        """
        Ensures that all referenced columns exist in the LazyFrame.
        """
        used_columns = expr.meta.root_names()
        available_columns = self.lazyframe.collect_schema().names()
        missing = [col for col in used_columns if col not in available_columns]

        if missing:
            raise ValueError(
                f"The following columns used in the query do not exist in the LazyFrame: {missing}"
            )

    def apply_selections(self) -> pl.LazyFrame:
        """
        Applies the selection expression to the LazyFrame.
        """
        lazyframe = self.lazyframe
        for selection in self.selections.values():
            expr = SelectionParser(selection).parse()
            self._validate_columns(expr)
            lazyframe = lazyframe.filter(expr)
        return lazyframe
