# Deterministic IDs shared by build_board.py and gen_schematic.py, so each footprint links to its schematic symbol.
import uuid

NS = uuid.UUID("5e5a3e00-0000-4000-8000-5e5a3ec0ffee")


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(map(str, parts))))


def symbol_uuid(ref):
    return uid("symbol", ref)
