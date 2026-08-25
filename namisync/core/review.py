"""Typed review-limit facts shared by planning and compact results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .scalars import MAX_SIGNED_64, require_safe_int, require_signed_64


class ReviewTreeKind(StrEnum):
    PLAN = "plan"
    INVENTORY = "inventory"


class ReviewPopulation(StrEnum):
    DOMAIN = "domain"
    INFORMATIONAL = "informational"


class ReviewLimitAxis(StrEnum):
    ROWS = "rows"
    RETAINED_BYTES = "retained-bytes"
    LOGICAL_BYTES = "logical-bytes"


@dataclass(frozen=True, slots=True)
class ReviewFactLimitExceeded:
    """Exact bounded fact explaining why no complete review was published."""

    reason: str
    tree_kind: ReviewTreeKind
    population: ReviewPopulation
    axis: ReviewLimitAxis
    row_limit: int | None
    byte_limit: int | None

    def __post_init__(self) -> None:
        if self.reason != "review_fact_limit_exceeded":
            raise ValueError("review fact reason is invalid")
        if not isinstance(self.tree_kind, ReviewTreeKind):
            raise TypeError("review tree_kind has the wrong type")
        if not isinstance(self.population, ReviewPopulation):
            raise TypeError("review population has the wrong type")
        if not isinstance(self.axis, ReviewLimitAxis):
            raise TypeError("review axis has the wrong type")
        if self.row_limit is not None:
            require_safe_int(self.row_limit, "review row_limit")
        if self.byte_limit is not None:
            require_signed_64(self.byte_limit, "review byte_limit")
        if self.axis is ReviewLimitAxis.ROWS:
            if self.row_limit != 120_000 or self.byte_limit is not None:
                raise ValueError("row review fact has invalid limits")
            return
        if self.row_limit is not None or self.byte_limit is None:
            raise ValueError("byte review fact has invalid nullability")
        if self.axis is ReviewLimitAxis.LOGICAL_BYTES:
            if (
                self.tree_kind is not ReviewTreeKind.PLAN
                or self.population is not ReviewPopulation.DOMAIN
                or self.byte_limit != MAX_SIGNED_64
            ):
                raise ValueError("logical-byte review fact is invalid")
            return
        expected = (
            134_217_728
            if self.tree_kind is ReviewTreeKind.PLAN
            and self.population is ReviewPopulation.DOMAIN
            else 201_326_592
        )
        if self.byte_limit != expected:
            raise ValueError("retained-byte review fact has the wrong limit")

    @classmethod
    def plan_logical_bytes(cls) -> "ReviewFactLimitExceeded":
        return cls(
            reason="review_fact_limit_exceeded",
            tree_kind=ReviewTreeKind.PLAN,
            population=ReviewPopulation.DOMAIN,
            axis=ReviewLimitAxis.LOGICAL_BYTES,
            row_limit=None,
            byte_limit=MAX_SIGNED_64,
        )


class ReviewFactLimitError(ValueError):
    """Raised before publication when a complete review cannot be represented."""

    def __init__(self, fact: ReviewFactLimitExceeded) -> None:
        super().__init__(fact.reason)
        self.fact = fact
