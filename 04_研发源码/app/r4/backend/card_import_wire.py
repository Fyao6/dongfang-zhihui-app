"""Lossless bounded fixed-worker wire decoding; no persistence or authority."""
import math

CODEC = 'card-import-dictionary-1'


def pack_wire(value):
    dictionary, indices = [], {}

    def key(text):
        if text not in indices:
            indices[text] = len(dictionary)
            dictionary.append(text)
        return indices[text]

    def encode(item):
        if isinstance(item, str):
            return [0, key(item)]
        if isinstance(item, list):
            return [1, *[encode(v) for v in item]]
        if isinstance(item, dict):
            result = [2]
            for name, data in item.items():
                result.extend((key(name), encode(data)))
            return result
        if item is None or type(item) in (bool, int) or type(item) is float and math.isfinite(item):
            return item
        raise ValueError('invalid_wire_value')

    encoded = encode(value)
    return {'codec': CODEC, 'dictionary': dictionary, 'result': encoded}


def decode_wire(wire):
    return worker_result({'ok': True, **wire})


def worker_result(response):
    if 'codec' not in response:
        return response['result']
    if response.get('codec') != CODEC or set(response) != {'ok', 'codec', 'dictionary', 'result'}:
        raise ValueError('invalid_worker_codec')
    dictionary = response['dictionary']
    if not isinstance(dictionary, list) or len(dictionary) > 500000 or any(not isinstance(s, str) for s in dictionary):
        raise ValueError('invalid_worker_dictionary')
    nodes = 0

    def text(index):
        if type(index) is not int or not 0 <= index < len(dictionary):
            raise ValueError('invalid_worker_dictionary_index')
        return dictionary[index]

    def decode(value, depth=0):
        nonlocal nodes
        nodes += 1
        if depth > 96 or nodes > 2000000:
            raise ValueError('invalid_worker_wire_bounds')
        if value is None or type(value) is bool or type(value) is int:
            return value
        if type(value) is float and math.isfinite(value):
            return value
        if not isinstance(value, list) or not value or type(value[0]) is not int:
            raise ValueError('invalid_worker_wire_value')
        tag = value[0]
        if tag == 0 and len(value) == 2:
            return text(value[1])
        if tag == 1:
            return [decode(v, depth + 1) for v in value[1:]]
        if tag == 2 and len(value) % 2 == 1:
            result = {}
            for index in range(1, len(value), 2):
                key = text(value[index])
                if key in result or key in {'__proto__', 'constructor', 'prototype'}:
                    raise ValueError('invalid_worker_wire_key')
                result[key] = decode(value[index + 1], depth + 1)
            return result
        raise ValueError('invalid_worker_wire_tag')

    return decode(response['result'])
