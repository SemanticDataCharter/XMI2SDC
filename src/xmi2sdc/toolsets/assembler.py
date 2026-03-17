"""Assembler Toolset — submits mapping plans to the SDCStudio Assembly API.

Transforms flat mapper output into the nested Assembly API request tree,
posts to the assembly endpoint, and polls until processing completes.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List

import httpx
from google.adk.tools import FunctionTool
from google.adk.tools.base_toolset import BaseToolset

from xmi2sdc.common.audit import AuditLogger
from xmi2sdc.common.cache import CacheManager
from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.common.exceptions import AssemblyApiError, InsufficientFundsError


def _component_to_mint_ref(component: Dict[str, Any]) -> Dict[str, str]:
    """Convert a flat mapper component to an Assembly API mint reference."""
    return {
        "label": component["label"],
        "data_type": component["sdc4_type"],
        "description": component.get("description", ""),
    }


def _build_class_clusters(
    components: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Build class clusters from components and is_cluster=true entries.

    Returns a dict keyed by cluster_name -> {label, components, clusters, description}.
    """
    # Index components by source_class
    components_by_class: Dict[str, List[Dict[str, str]]] = {}
    for comp in components:
        source = comp.get("source_class", "")
        if source:
            components_by_class.setdefault(source, []).append(_component_to_mint_ref(comp))

    # Build class cluster nodes from is_cluster=true entries (plain class clusters)
    # and from standalone cluster entries (no is_cluster, no containment_type)
    class_clusters: Dict[str, Dict[str, Any]] = {}
    for cl in clusters:
        name = cl["cluster_name"]
        has_containment = "containment_type" in cl
        is_cluster_flag = cl.get("is_cluster", False)

        if has_containment:
            # Composition/aggregation/association clusters are handled later
            continue

        if is_cluster_flag or not has_containment:
            # Plain class cluster
            if name not in class_clusters:
                class_clusters[name] = {
                    "label": name,
                    "components": components_by_class.get(name, []),
                    "clusters": [],
                    "description": cl.get("description", ""),
                }

    # Also create class clusters for components whose source_class has no cluster entry
    for source_class, comp_refs in components_by_class.items():
        if source_class not in class_clusters:
            class_clusters[source_class] = {
                "label": source_class,
                "components": comp_refs,
                "clusters": [],
                "description": "",
            }

    return class_clusters


def _apply_composition_nesting(
    class_clusters: Dict[str, Dict[str, Any]],
    clusters: List[Dict[str, Any]],
) -> set:
    """Nest child clusters under parent for composition relationships.

    Returns the set of cluster names that were nested (should be removed
    from top-level).
    """
    nested: set = set()
    for cl in clusters:
        if cl.get("containment_type") != "composition":
            continue
        parent_name = cl["cluster_name"]
        child_refs = cl.get("component_refs", [])
        parent = class_clusters.get(parent_name)
        if parent is None:
            continue
        for child_name in child_refs:
            child = class_clusters.get(child_name)
            if child is not None:
                parent["clusters"].append(child)
                nested.add(child_name)
    return nested


def _build_association_clusters(
    clusters: List[Dict[str, Any]],
    class_clusters: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build standalone clusters for aggregation and association relationships."""
    result: List[Dict[str, Any]] = []
    for cl in clusters:
        ct = cl.get("containment_type", "")
        if ct not in ("aggregation", "association", "plain"):
            continue
        name = cl["cluster_name"]
        child_refs = cl.get("component_refs", [])

        # Aggregation: reference child clusters but keep them top-level too
        # Association/plain: role components already exist as XdString in components
        node = {
            "label": f"{name}_assoc",
            "components": [],
            "clusters": [],
            "description": cl.get("description", ""),
        }
        for ref in child_refs:
            child = class_clusters.get(ref)
            if child is not None:
                node["clusters"].append(child)
            else:
                # Role component — create as XdString mint ref
                node["components"].append(
                    {"label": ref, "data_type": "XdString", "description": ""}
                )
        result.append(node)
    return result


class SdcAssemblerToolset(BaseToolset):
    """Toolset for submitting mapping plans to the SDCStudio Assembly API."""

    def __init__(self, config: XMI2SDCConfig, **kwargs: Any):
        super().__init__(**kwargs)
        self._config = config
        self._cache = CacheManager(config.cache.root)
        self._cache.ensure_dirs()
        self._audit = AuditLogger(config.audit.path, config.audit.log_level)

    async def get_tools(self, readonly_context=None) -> list:
        """Return the assembler FunctionTools."""
        tools = [
            FunctionTool(self.build_assembly_tree),
            FunctionTool(self.execute_assembly),
            FunctionTool(self.poll_status),
        ]
        if readonly_context and self.tool_filter:
            return [t for t in tools if self._is_tool_selected(t, readonly_context)]
        return tools

    async def build_assembly_tree(self, mapping_plan: dict) -> dict:
        """Transform a flat mapping plan into a nested Assembly API request tree.

        Args:
            mapping_plan: Output from the mapper toolset containing
                components, clusters, and model_name.

        Returns:
            Nested dict suitable as the ``data`` field of the Assembly API request.
        """
        start = time.monotonic()

        components = mapping_plan.get("components", [])
        clusters = mapping_plan.get("clusters", [])
        model_name = mapping_plan.get("model_name", "Model")

        # Step 1-2: Build class clusters with their components
        class_clusters = _build_class_clusters(components, clusters)

        # Step 3: Apply composition nesting
        nested = _apply_composition_nesting(class_clusters, clusters)

        # Step 4: Build association/aggregation clusters
        assoc_clusters = _build_association_clusters(clusters, class_clusters)

        # Step 5: Collect top-level items (not nested)
        top_level = [cl for name, cl in class_clusters.items() if name not in nested]
        top_level.extend(assoc_clusters)

        # Collect any top-level components not attached to a class
        top_components = [
            _component_to_mint_ref(c) for c in components if not c.get("source_class")
        ]

        result = {
            "label": model_name,
            "components": top_components,
            "clusters": top_level,
        }

        # Cache the assembly tree
        cache_path = self._cache.assembly_path(model_name)
        cache_path.write_text(json.dumps(result, indent=2))

        self._audit.log(
            agent="assembler",
            tool="build_assembly_tree",
            inputs={"model_name": model_name},
            outputs=result,
            start_time=start,
        )
        return result

    async def execute_assembly(
        self,
        title: str,
        description: str,
        assembly_tree: dict,
    ) -> dict:
        """Submit an assembly request to the SDCStudio Assembly API.

        Args:
            title: Title for the new data model.
            description: Description for the new data model.
            assembly_tree: Nested tree from build_assembly_tree.

        Returns:
            Dict with ``status``, ``data_source_ct_id``, and API response data.

        Raises:
            AssemblyApiError: On 400 or other unexpected API errors.
            InsufficientFundsError: On HTTP 402 (wallet balance too low).
        """
        start = time.monotonic()

        base_url = self._config.sdcstudio.base_url.rstrip("/")
        url = f"{base_url}/api/v1/dmgen/assemble/"
        token = self._config.sdcstudio.token

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Token {token}"

        body = {
            "title": title,
            "description": description,
            "data": assembly_tree,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body, headers=headers)

        result: Dict[str, Any]
        if response.status_code == 402:
            raise InsufficientFundsError(f"Insufficient wallet funds: {response.text}")
        elif response.status_code == 400:
            raise AssemblyApiError(f"Assembly validation error: {response.text}")
        elif response.status_code in (200, 201):
            data = response.json()
            result = {
                "status": "completed",
                "data_source_ct_id": data.get("ct_id", ""),
                "response": data,
            }
        elif response.status_code == 202:
            data = response.json()
            result = {
                "status": "processing",
                "data_source_ct_id": data.get("ct_id", ""),
                "response": data,
            }
        else:
            raise AssemblyApiError(f"Unexpected status {response.status_code}: {response.text}")

        self._audit.log(
            agent="assembler",
            tool="execute_assembly",
            inputs={"title": title, "description": description},
            outputs=result,
            start_time=start,
        )
        return result

    async def poll_status(
        self,
        data_source_ct_id: str,
        timeout_seconds: int = 300,
    ) -> dict:
        """Poll the data source status until processing completes.

        Args:
            data_source_ct_id: The ct_id returned by execute_assembly.
            timeout_seconds: Maximum wait time before raising an error.

        Returns:
            Dict with ``status`` and ``analysis_results`` on completion.

        Raises:
            AssemblyApiError: On timeout or terminal error states.
        """
        start = time.monotonic()

        base_url = self._config.sdcstudio.base_url.rstrip("/")
        url = f"{base_url}/uploader/api/data-sources/{data_source_ct_id}/"
        token = self._config.sdcstudio.token

        headers: Dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Token {token}"

        terminal_states = {"completed", "error", "agent_error"}
        deadline = time.monotonic() + timeout_seconds

        async with httpx.AsyncClient(timeout=15.0) as client:
            while True:
                if time.monotonic() > deadline:
                    raise AssemblyApiError(
                        f"Polling timed out after {timeout_seconds}s "
                        f"for data source {data_source_ct_id}"
                    )

                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    raise AssemblyApiError(
                        f"Poll request failed with status {response.status_code}: "
                        f"{response.text}"
                    )

                data = response.json()
                status = data.get("status", "").lower()

                if status in terminal_states:
                    result = {
                        "status": status,
                        "analysis_results": data.get("analysis_results"),
                        "response": data,
                    }
                    if status in ("error", "agent_error"):
                        self._audit.log(
                            agent="assembler",
                            tool="poll_status",
                            inputs={"data_source_ct_id": data_source_ct_id},
                            outputs=result,
                            start_time=start,
                        )
                        raise AssemblyApiError(
                            f"Assembly failed with status '{status}': "
                            f"{data.get('error_message', 'unknown error')}"
                        )

                    self._audit.log(
                        agent="assembler",
                        tool="poll_status",
                        inputs={"data_source_ct_id": data_source_ct_id},
                        outputs=result,
                        start_time=start,
                    )
                    return result

                await asyncio.sleep(5)
