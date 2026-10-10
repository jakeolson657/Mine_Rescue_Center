"""Identification of Parts practice data.

pages/parts_data.json is generated from the bench contest rules by
quiz_pipeline/build_parts_id.py: one entry per apparatus, each with its
assemblies in rules order, every assembly a diagram plus its numbered parts.
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / 'parts_data.json'


@lru_cache(maxsize=1)
def parts_units():
    with open(DATA_FILE, encoding='utf-8') as f:
        return json.load(f)


def unit_for_apparatus(name):
    """The parts unit whose match words appear in a BenchingApparatus name."""
    lowered = name.lower()
    for unit in parts_units():
        if any(word in lowered for word in unit['match']):
            return unit
    return None


def find_assembly(unit_slug, assembly_slug):
    """(unit, assembly) for the slugs, or (None, None)."""
    for unit in parts_units():
        if unit['slug'] == unit_slug:
            for assembly in unit['assemblies']:
                if assembly['slug'] == assembly_slug:
                    return unit, assembly
    return None, None
