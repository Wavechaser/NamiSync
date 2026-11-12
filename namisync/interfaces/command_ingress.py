"""Dependency-free whole-request admission for command-line adapters."""

MAX_COMMAND_ENVELOPE_BYTES = 65_536
INVALID_COMMAND_REQUEST = "Invalid command request."


def arguments_within_ingress_bound(arguments: list[str]) -> bool:
    total = 0
    for index, argument in enumerate(arguments):
        if type(argument) is not str:
            return False
        try:
            encoded_size = len(argument.encode("utf-8"))
        except UnicodeEncodeError:
            return False
        total += encoded_size + (index > 0)
        if total > MAX_COMMAND_ENVELOPE_BYTES:
            return False
    return True
