import json
from concurrent.futures import ThreadPoolExecutor

from app.services.simulation_runner import SimulationRunState, SimulationRunner


def test_run_state_writes_remain_valid_under_concurrency(tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    SimulationRunner._run_states.clear()
    state = SimulationRunState(simulation_id="sim_atomic", total_rounds=10)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: SimulationRunner._save_run_state(state), range(40)))

    state_path = tmp_path / state.simulation_id / "run_state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["simulation_id"] == state.simulation_id
    assert data["total_rounds"] == 10
    assert list(state_path.parent.glob(".run_state_*.tmp")) == []
