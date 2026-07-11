from types import SimpleNamespace

import pytest

from app.services import graph_builder as graph_builder_module
from app.services.forecast_service import ForecastService
from app.services.graph_builder import GraphBuilderService


def test_graph_info_reports_nonempty_untyped_graph(monkeypatch):
    nodes = [
        SimpleNamespace(labels=[]),
        SimpleNamespace(labels=["Entity"]),
        SimpleNamespace(labels=None),
    ]
    edges = [SimpleNamespace(), SimpleNamespace()]
    monkeypatch.setattr(
        graph_builder_module, "fetch_all_nodes", lambda client, graph_id: nodes
    )
    monkeypatch.setattr(
        graph_builder_module, "fetch_all_edges", lambda client, graph_id: edges
    )
    builder = object.__new__(GraphBuilderService)
    builder.client = object()

    info = builder._get_graph_info("graph-untyped")

    assert info.node_count == 3
    assert info.edge_count == 2
    assert info.entity_types == []


def test_graph_info_collects_custom_entity_labels(monkeypatch):
    nodes = [
        SimpleNamespace(labels=["Entity", "HotelProperty"]),
        SimpleNamespace(labels=["Node", "GuestSegment"]),
        SimpleNamespace(labels=["HotelProperty"]),
    ]
    monkeypatch.setattr(
        graph_builder_module, "fetch_all_nodes", lambda client, graph_id: nodes
    )
    monkeypatch.setattr(
        graph_builder_module, "fetch_all_edges", lambda client, graph_id: []
    )
    builder = object.__new__(GraphBuilderService)
    builder.client = object()

    info = builder._get_graph_info("graph-typed")

    assert set(info.entity_types) == {"HotelProperty", "GuestSegment"}


def test_graph_validation_distinguishes_empty_graph():
    info = SimpleNamespace(node_count=0, edge_count=0, entity_types=[])

    with pytest.raises(RuntimeError, match="extracted no entities"):
        ForecastService._validate_graph_for_simulation(info)


def test_graph_validation_explains_nonempty_untyped_graph():
    info = SimpleNamespace(node_count=15, edge_count=16, entity_types=[])

    with pytest.raises(RuntimeError) as exc_info:
        ForecastService._validate_graph_for_simulation(info)

    message = str(exc_info.value)
    assert "15 entities and 16 relationships" in message
    assert "classified 0 entities" in message
    assert "daily reservation/performance data" in message


def test_graph_validation_accepts_typed_graph():
    info = SimpleNamespace(
        node_count=3,
        edge_count=2,
        entity_types=["HotelProperty"],
    )

    ForecastService._validate_graph_for_simulation(info)


def test_graph_batch_upload_reports_incremental_episode_checkpoints(monkeypatch):
    batches = []
    next_episode = [0]

    def add_batch(graph_id, episodes):
        result = []
        for _ in episodes:
            next_episode[0] += 1
            result.append(SimpleNamespace(uuid_=f"episode_{next_episode[0]}"))
        return result

    builder = object.__new__(GraphBuilderService)
    builder.client = SimpleNamespace(
        graph=SimpleNamespace(add_batch=add_batch)
    )
    monkeypatch.setattr(graph_builder_module.time, "sleep", lambda _: None)

    episode_ids = builder.add_text_batches(
        "graph_123",
        ["one", "two", "three", "four"],
        batch_size=2,
        checkpoint_callback=lambda ids: batches.append(ids),
    )

    assert episode_ids == ["episode_1", "episode_2", "episode_3", "episode_4"]
    assert batches == [
        ["episode_1", "episode_2"],
        ["episode_1", "episode_2", "episode_3", "episode_4"],
    ]
