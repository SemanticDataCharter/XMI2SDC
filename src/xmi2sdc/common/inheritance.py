"""Inheritance flattening for parsed UML models.

SDC4 uses xsd:restriction only — every component must be self-contained.
This module walks generalization chains and merges ancestor attributes
so that each class carries the full set of attributes it needs.
"""

from __future__ import annotations


class CyclicInheritanceError(Exception):
    """Raised when a circular inheritance chain is detected."""


def flatten_inheritance(parsed_model: dict) -> dict:
    """Walk generalization chains and merge ancestor attributes into all_attributes.

    Mutates classes in-place, populating ``all_attributes`` (inherited + own,
    root-first order) and ``ancestor_xmi_ids`` (transitive ancestor chain).

    Args:
        parsed_model: Dict representation of a ParsedXmiModel.

    Returns:
        The same dict, with classes mutated.

    Raises:
        CyclicInheritanceError: If a circular inheritance chain is detected.
    """
    # Build xmi_id → class dict lookup across all classes
    class_map: dict[str, dict] = {}
    all_classes = _collect_all_classes(parsed_model)
    for cls in all_classes:
        xmi_id = cls.get("xmi_id", "")
        if xmi_id:
            class_map[xmi_id] = cls

    # Flatten each class
    cache: dict[str, list[dict]] = {}  # xmi_id → resolved all_attributes
    for cls in all_classes:
        _resolve_class(cls, class_map, cache, set())

    return parsed_model


def _resolve_class(
    cls: dict,
    class_map: dict[str, dict],
    cache: dict[str, list[dict]],
    visiting: set[str],
) -> list[dict]:
    """Recursively resolve all_attributes for a class.

    Args:
        cls: The class dict to resolve.
        class_map: xmi_id → class dict lookup.
        cache: Already-resolved xmi_id → all_attributes.
        visiting: Set of xmi_ids currently being resolved (cycle detection).

    Returns:
        The resolved all_attributes list for this class.
    """
    xmi_id = cls.get("xmi_id", "")

    # Already resolved
    if xmi_id in cache:
        cls["all_attributes"] = cache[xmi_id]
        return cache[xmi_id]

    # Cycle detection
    if xmi_id in visiting:
        raise CyclicInheritanceError(
            f"Circular inheritance detected involving class '{cls.get('name', xmi_id)}' "
            f"(xmi_id={xmi_id})"
        )
    visiting.add(xmi_id)

    # Collect inherited attributes from all parents (in order)
    inherited: list[dict] = []
    ancestor_ids: list[str] = []
    for parent_id in cls.get("parent_xmi_ids", []):
        parent = class_map.get(parent_id)
        if parent is None:
            continue
        # Recursively resolve parent first
        parent_attrs = _resolve_class(parent, class_map, cache, visiting)
        # Collect ancestors: parent's ancestors + parent itself
        for aid in parent.get("ancestor_xmi_ids", []):
            if aid not in ancestor_ids:
                ancestor_ids.append(aid)
        if parent_id not in ancestor_ids:
            ancestor_ids.append(parent_id)
        # Merge parent's all_attributes (avoiding duplicates by name)
        existing_names = {a["name"] for a in inherited}
        for attr in parent_attrs:
            if attr["name"] not in existing_names:
                inherited.append(attr)
                existing_names.add(attr["name"])

    # Own attributes override inherited ones with the same name
    own_attrs = cls.get("attributes", [])
    own_names = {a["name"] for a in own_attrs}
    merged = [a for a in inherited if a["name"] not in own_names]
    merged.extend(own_attrs)

    cls["all_attributes"] = merged
    cls["ancestor_xmi_ids"] = ancestor_ids

    visiting.discard(xmi_id)
    cache[xmi_id] = merged
    return merged


def _collect_all_classes(parsed_model: dict) -> list[dict]:
    """Flatten all classes from packages and top-level."""
    result = list(parsed_model.get("top_level_classes", []))
    for pkg in parsed_model.get("packages", []):
        result.extend(_collect_classes_from_package(pkg))
    return result


def _collect_classes_from_package(pkg: dict) -> list[dict]:
    """Recursively collect classes from a package dict."""
    result = list(pkg.get("classes", []))
    for sub in pkg.get("sub_packages", []):
        result.extend(_collect_classes_from_package(sub))
    return result
