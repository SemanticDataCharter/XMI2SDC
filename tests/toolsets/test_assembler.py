"""Tests for SdcAssemblerToolset."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from xmi2sdc.common.config import XMI2SDCConfig
from xmi2sdc.common.exceptions import AssemblyApiError, InsufficientFundsError
from xmi2sdc.toolsets.assembler import (
    SdcAssemblerToolset,
    _build_class_clusters,
    _component_to_mint_ref,
)


@pytest.fixture
def assembler(tmp_path):
    config = XMI2SDCConfig(
        cache={"root": str(tmp_path / "cache")},
        audit={"path": str(tmp_path / "cache" / "audit.jsonl")},
        sdcstudio={"base_url": "http://test:8000", "api_key": "test-token"},
    )
    return SdcAssemblerToolset(config=config)


# ---------------------------------------------------------------------------
# component_to_mint_ref
# ---------------------------------------------------------------------------


def test_component_to_mint_ref_basic():
    comp = {"label": "Cat.name", "sdc4_type": "XdString", "description": "Name of the cat"}
    ref = _component_to_mint_ref(comp)
    assert ref == {"label": "Cat.name", "data_type": "XdString", "description": "Name of the cat"}


def test_component_to_mint_ref_no_description():
    comp = {"label": "X.val", "sdc4_type": "XdQuantity"}
    ref = _component_to_mint_ref(comp)
    assert ref["description"] == ""


def test_component_to_mint_ref_all_sdc4_types():
    for sdc_type in ("XdString", "XdBoolean", "XdCount", "XdQuantity", "XdTemporal"):
        ref = _component_to_mint_ref({"label": "test", "sdc4_type": sdc_type})
        assert ref["data_type"] == sdc_type


# ---------------------------------------------------------------------------
# build_assembly_tree — unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_tree_simple_class(assembler, simple_mapping_plan):
    tree = await assembler.build_assembly_tree(simple_mapping_plan)
    assert tree["label"] == "SimpleModel"
    assert len(tree["clusters"]) == 1
    person = tree["clusters"][0]
    assert person["label"] == "Person"
    assert len(person["components"]) == 2
    labels = {c["label"] for c in person["components"]}
    assert labels == {"Person.name", "Person.birthDate"}


@pytest.mark.asyncio
async def test_build_tree_composition_nesting(assembler, vehicle_mapping_plan):
    tree = await assembler.build_assembly_tree(vehicle_mapping_plan)
    assert tree["label"] == "VehicleModel"
    # Vehicle is top-level, Engine and Wheel are nested
    assert len(tree["clusters"]) == 1
    vehicle = tree["clusters"][0]
    assert vehicle["label"] == "Vehicle"
    assert len(vehicle["components"]) == 3
    nested_labels = {c["label"] for c in vehicle["clusters"]}
    assert nested_labels == {"Engine", "Wheel"}


@pytest.mark.asyncio
async def test_build_tree_nested_components(assembler, vehicle_mapping_plan):
    tree = await assembler.build_assembly_tree(vehicle_mapping_plan)
    vehicle = tree["clusters"][0]
    engine = next(c for c in vehicle["clusters"] if c["label"] == "Engine")
    assert len(engine["components"]) == 2
    types = {c["data_type"] for c in engine["components"]}
    assert "XdQuantity" in types
    assert "XdBoolean" in types


@pytest.mark.asyncio
async def test_build_tree_empty_mapping(assembler):
    plan = {"model_name": "Empty", "components": [], "clusters": []}
    tree = await assembler.build_assembly_tree(plan)
    assert tree["label"] == "Empty"
    assert tree["clusters"] == []
    assert tree["components"] == []


@pytest.mark.asyncio
async def test_build_tree_association_cluster(assembler):
    plan = {
        "model_name": "AssocTest",
        "components": [
            {"source_class": "Student", "label": "Student.name", "sdc4_type": "XdString"},
            {"source_class": "Course", "label": "Course.title", "sdc4_type": "XdString"},
        ],
        "clusters": [
            {
                "cluster_name": "Student",
                "source_xmi_id": "s1",
                "description": "",
                "component_refs": [],
            },
            {
                "cluster_name": "Course",
                "source_xmi_id": "c1",
                "description": "",
                "component_refs": [],
            },
            {
                "is_cluster": True,
                "cluster_name": "Enrollment",
                "source_xmi_id": "a1",
                "description": "Student enrolls in Course",
                "component_refs": ["student_role", "course_role"],
                "containment_type": "association",
            },
        ],
    }
    tree = await assembler.build_assembly_tree(plan)
    # Student, Course are top-level; association cluster also present
    labels = {c["label"] for c in tree["clusters"]}
    assert "Student" in labels
    assert "Course" in labels
    assert "Enrollment_assoc" in labels


@pytest.mark.asyncio
async def test_build_tree_aggregation_cluster(assembler):
    plan = {
        "model_name": "AggTest",
        "components": [
            {"source_class": "Fleet", "label": "Fleet.name", "sdc4_type": "XdString"},
            {"source_class": "Ship", "label": "Ship.name", "sdc4_type": "XdString"},
        ],
        "clusters": [
            {
                "cluster_name": "Fleet",
                "source_xmi_id": "f1",
                "description": "",
                "component_refs": [],
            },
            {
                "cluster_name": "Ship",
                "source_xmi_id": "s1",
                "description": "",
                "component_refs": [],
            },
            {
                "is_cluster": True,
                "cluster_name": "Fleet",
                "source_xmi_id": "agg1",
                "description": "Fleet contains Ships",
                "component_refs": ["Ship"],
                "containment_type": "aggregation",
            },
        ],
    }
    tree = await assembler.build_assembly_tree(plan)
    labels = {c["label"] for c in tree["clusters"]}
    assert "Fleet" in labels
    assert "Ship" in labels
    assert "Fleet_assoc" in labels


@pytest.mark.asyncio
async def test_build_tree_caches_result(assembler, simple_mapping_plan, tmp_path):
    await assembler.build_assembly_tree(simple_mapping_plan)
    cache_path = tmp_path / "cache" / "assemblies" / "SimpleModel.json"
    assert cache_path.is_file()
    cached = json.loads(cache_path.read_text())
    assert cached["label"] == "SimpleModel"


@pytest.mark.asyncio
async def test_build_tree_top_level_components(assembler):
    plan = {
        "model_name": "TopComp",
        "components": [
            {"label": "orphan_field", "sdc4_type": "XdString", "description": "No class"},
        ],
        "clusters": [],
    }
    tree = await assembler.build_assembly_tree(plan)
    assert len(tree["components"]) == 1
    assert tree["components"][0]["label"] == "orphan_field"


@pytest.mark.asyncio
async def test_build_tree_enum_component(assembler):
    plan = {
        "model_name": "EnumTest",
        "components": [
            {
                "source_class": "Item",
                "label": "Item.status",
                "sdc4_type": "XdString",
                "description": "Status enum",
            },
        ],
        "clusters": [
            {
                "cluster_name": "Item",
                "source_xmi_id": "i1",
                "description": "",
                "component_refs": [],
            },
        ],
    }
    tree = await assembler.build_assembly_tree(plan)
    item = tree["clusters"][0]
    assert item["components"][0]["data_type"] == "XdString"


@pytest.mark.asyncio
async def test_build_tree_inheritance_flattened(assembler):
    """Inheritance is flattened by the mapper — all attributes on the subclass."""
    plan = {
        "model_name": "InheritTest",
        "components": [
            {
                "source_class": "Dog",
                "label": "Dog.name",
                "sdc4_type": "XdString",
                "description": "inherited",
            },
            {
                "source_class": "Dog",
                "label": "Dog.breed",
                "sdc4_type": "XdString",
                "description": "own",
            },
        ],
        "clusters": [
            {
                "cluster_name": "Dog",
                "source_xmi_id": "d1",
                "description": "A dog",
                "component_refs": [],
            },
        ],
    }
    tree = await assembler.build_assembly_tree(plan)
    dog = tree["clusters"][0]
    assert len(dog["components"]) == 2


# ---------------------------------------------------------------------------
# _build_class_clusters helper
# ---------------------------------------------------------------------------


def test_build_class_clusters_creates_from_components():
    components = [
        {"source_class": "Foo", "label": "Foo.x", "sdc4_type": "XdString"},
    ]
    clusters = []
    result = _build_class_clusters(components, clusters)
    assert "Foo" in result
    assert len(result["Foo"]["components"]) == 1


def test_build_class_clusters_skips_containment():
    components = []
    clusters = [
        {"cluster_name": "A", "source_xmi_id": "1", "description": "", "component_refs": []},
        {"cluster_name": "A", "containment_type": "composition", "component_refs": ["B"]},
    ]
    result = _build_class_clusters(components, clusters)
    assert "A" in result
    assert len(result) == 1  # only one class cluster, not the composition entry


# ---------------------------------------------------------------------------
# execute_assembly — mocked httpx
# ---------------------------------------------------------------------------


def _mock_response(status_code, json_data):
    response = httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("POST", "http://test:8000/api/v1/dmgen/assemble/"),
    )
    return response


@pytest.mark.asyncio
async def test_execute_assembly_202(assembler):
    mock_resp = _mock_response(202, {"ct_id": "abc123", "status": "processing"})
    with patch("xmi2sdc.toolsets.assembler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await assembler.execute_assembly("Test", "desc", {"label": "M"})
        assert result["status"] == "processing"
        assert result["data_source_ct_id"] == "abc123"


@pytest.mark.asyncio
async def test_execute_assembly_200(assembler):
    mock_resp = _mock_response(200, {"ct_id": "xyz789", "status": "completed"})
    with patch("xmi2sdc.toolsets.assembler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await assembler.execute_assembly("Test", "desc", {"label": "M"})
        assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_execute_assembly_400(assembler):
    mock_resp = _mock_response(400, {"error": "bad request"})
    with patch("xmi2sdc.toolsets.assembler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(AssemblyApiError, match="validation error"):
            await assembler.execute_assembly("Test", "desc", {"label": "M"})


@pytest.mark.asyncio
async def test_execute_assembly_402_uses_the_servers_message(assembler):
    """
    The server writes a good sentence, quoted in credits. We surface it rather
    than prefixing our own and dumping the raw body at the user.
    """
    mock_resp = _mock_response(
        402,
        {
            "error": "Insufficient credits. This needs 500 credits; you have 200.",
            "error_type": "insufficient_funds",
            "estimated_cost_credits": 500,
            "balance_credits": 200,
            "estimated_cost": "0.50",
            "balance": "0.20",
        },
    )
    with patch("xmi2sdc.toolsets.assembler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(InsufficientFundsError) as exc:
            await assembler.execute_assembly("Test", "desc", {"label": "M"})

    err = exc.value
    assert str(err) == "Insufficient credits. This needs 500 credits; you have 200."
    assert "wallet funds" not in str(err), "the dollar-era prefix is gone"
    assert "{" not in str(err), "the raw body is no longer dumped at the user"
    # credits carried from the server, not re-derived
    assert err.estimated_cost_credits == 500
    assert err.balance_credits == 200


@pytest.mark.asyncio
async def test_execute_assembly_402_falls_back_when_body_is_not_json(assembler):
    """An older or misbehaving server must still produce a usable error."""
    mock_resp = httpx.Response(
        status_code=402,
        content=b"payment required",  # not JSON, so .json() raises
        request=httpx.Request("POST", "http://test:8000/api/v1/dmgen/assemble/"),
    )
    with patch("xmi2sdc.toolsets.assembler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(InsufficientFundsError, match="Insufficient credits"):
            await assembler.execute_assembly("Test", "desc", {"label": "M"})


# ---------------------------------------------------------------------------
# poll_status — mocked httpx
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_status_completed(assembler):
    mock_resp = httpx.Response(
        200,
        json={"status": "completed", "analysis_results": {"components": 5}},
        request=httpx.Request("GET", "http://test:8000/uploader/api/data-sources/abc/"),
    )
    with patch("xmi2sdc.toolsets.assembler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await assembler.poll_status("abc")
        assert result["status"] == "completed"
        assert result["analysis_results"] == {"components": 5}


@pytest.mark.asyncio
async def test_poll_status_error(assembler):
    mock_resp = httpx.Response(
        200,
        json={"status": "error", "error_message": "parse failed"},
        request=httpx.Request("GET", "http://test:8000/uploader/api/data-sources/abc/"),
    )
    with patch("xmi2sdc.toolsets.assembler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(AssemblyApiError, match="parse failed"):
            await assembler.poll_status("abc")


@pytest.mark.asyncio
async def test_poll_status_timeout(assembler):
    """Poll should raise on timeout when status never becomes terminal."""
    mock_resp = httpx.Response(
        200,
        json={"status": "processing"},
        request=httpx.Request("GET", "http://test:8000/uploader/api/data-sources/abc/"),
    )
    with patch("xmi2sdc.toolsets.assembler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Use a very short timeout to avoid slow tests
        with patch("xmi2sdc.toolsets.assembler.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AssemblyApiError, match="timed out"):
                await assembler.poll_status("abc", timeout_seconds=0)


# ---------------------------------------------------------------------------
# get_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tools_returns_three(assembler):
    tools = await assembler.get_tools()
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert names == {"build_assembly_tree", "execute_assembly", "poll_status"}
