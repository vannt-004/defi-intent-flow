import re
from copy import deepcopy


CAMEL_TO_SNAKE_OVERRIDES = {
    "apy": "apy",
    "apr": "apr",
}


def snake_to_camel_key(key: str) -> str:
    if key == "_id" or "_" not in key:
        return key
    parts = key.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def camel_to_snake_key(key: str) -> str:
    if key == "_id" or "_" in key:
        return key
    if key in CAMEL_TO_SNAKE_OVERRIDES:
        return CAMEL_TO_SNAKE_OVERRIDES[key]
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()


def keys_to_camel(value):
    return _convert_keys(value, snake_to_camel_key)


def keys_to_snake(value):
    return _convert_keys(value, camel_to_snake_key)


MAX_MONGO_INT64 = 2**63 - 1
MIN_MONGO_INT64 = -(2**63)


def sanitize_mongo_numbers(value, key: str | None = None):
    if isinstance(value, list):
        return [sanitize_mongo_numbers(item, key) for item in value]
    if isinstance(value, dict):
        return {
            item_key: sanitize_mongo_numbers(item_value, item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, bool) or not isinstance(value, int):
        return value
    if MIN_MONGO_INT64 <= value <= MAX_MONGO_INT64:
        return value

    normalized_key = (key or "").lower()
    if "raw" in normalized_key or normalized_key.endswith("id"):
        return str(value)
    return float(value)


def _convert_keys(value, converter):
    if isinstance(value, list):
        return [_convert_keys(item, converter) for item in value]
    if not isinstance(value, dict):
        return value

    result = {}
    for key, item in deepcopy(value).items():
        result[converter(key)] = _convert_keys(item, converter)
    return result
