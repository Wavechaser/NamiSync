"""Wire representation of workflow availability totals."""

from dataclasses import asdict
from namisync.workflows import RecallSummary


def recall_summary_wire(summary: RecallSummary) -> dict[str, object]:
    value = asdict(summary)
    value["size"] = None if summary.size is None else str(summary.size)
    return value


