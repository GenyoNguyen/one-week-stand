from types import SimpleNamespace

from app.services.zep_entity_reader import ZepEntityReader


def test_get_node_edges_uses_current_zep_sdk_method():
    calls = []
    edge = SimpleNamespace(
        uuid_="edge-1",
        name="WORKS_AT",
        fact="Person works at Company",
        source_node_uuid="node-1",
        target_node_uuid="node-2",
        attributes={"since": 2024},
    )
    reader = object.__new__(ZepEntityReader)
    reader.client = SimpleNamespace(
        graph=SimpleNamespace(
            node=SimpleNamespace(
                get_edges=lambda node_uuid: calls.append(node_uuid) or [edge]
            )
        )
    )

    result = reader.get_node_edges("node-1")

    assert calls == ["node-1"]
    assert result == [{
        "uuid": "edge-1",
        "name": "WORKS_AT",
        "fact": "Person works at Company",
        "source_node_uuid": "node-1",
        "target_node_uuid": "node-2",
        "attributes": {"since": 2024},
    }]
