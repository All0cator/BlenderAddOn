from .bad_globals import *

def contains_prefix(name : str) -> bool:
    return name.startswith(BAD_PREFIX)

def get_name_from_prefixed_name(prefixed_name : str) -> str:
    return prefixed_name[len(BAD_PREFIX):]