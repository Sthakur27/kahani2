import game


def _choice(run, label):
    return next(c for c in run["choices"] if c["label"] == label)


def test_band_for():
    assert game.band_for(20, 0, 15) == "crit_success"
    assert game.band_for(1, 5, 2) == "crit_fail"
    assert game.band_for(10, 2, 12) == "success"   # 12 >= 12
    assert game.band_for(10, 2, 13) == "fail"       # 12 < 13


def test_start_run_uses_class_preset(client, auth, campaign):
    headers, _ = auth()
    r = client.post(f"/api/stories/{campaign['story_id']}/runs",
                    json={"char_class": "warrior"}, headers=headers)
    assert r.status_code == 201
    ch = r.json()["snapshot"]["characters"][0]
    assert ch["hp"] == 28 and ch["stats"]["str"] == 15


def test_start_run_bad_class(client, auth, campaign):
    headers, _ = auth()
    r = client.post(f"/api/stories/{campaign['story_id']}/runs",
                    json={"char_class": "wizardx"}, headers=headers)
    assert r.status_code == 400


def test_take_edge_applies_effect(client, auth, campaign):
    headers, _ = auth()
    sid = campaign["story_id"]
    run = client.post(f"/api/stories/{sid}/runs", json={"char_class": "warrior"}, headers=headers).json()
    edge = _choice(run, "Step forward")["edge_id"]
    r = client.post(f"/api/runs/{run['id']}/take/{edge}", headers=headers)
    assert r.status_code == 200
    assert r.json()["snapshot"]["characters"][0]["hp"] == 23  # 28 - 5


def test_death_and_block(client, auth, db, campaign):
    from storybuilder import add_branch
    headers, _ = auth()
    sid = campaign["story_id"]
    add_branch(db, story_id=sid, from_node_id=None, author_id=campaign["author_id"],
               label="Touch the trap", content="zap",
               effects=[{"type": "hp_delta", "amount": -100}])
    db.commit()
    run = client.post(f"/api/stories/{sid}/runs", json={"char_class": "warrior"}, headers=headers).json()
    edge = _choice(run, "Touch the trap")["edge_id"]
    r = client.post(f"/api/runs/{run['id']}/take/{edge}", headers=headers).json()
    assert r["status"] == "dead"
    assert r["snapshot"]["characters"][0]["hp"] == 0
    blocked = client.post(f"/api/runs/{run['id']}/take/{edge}", headers=headers)
    assert blocked.status_code == 409


def test_starting_kit_use_item(client, auth, campaign):
    headers, _ = auth()
    sid = campaign["story_id"]
    run = client.post(f"/api/stories/{sid}/runs", json={"char_class": "warrior"}, headers=headers).json()
    assert any(i["slug"] == "health_potion" for i in run["inventory"])
    edge = _choice(run, "Step forward")["edge_id"]
    r = client.post(f"/api/runs/{run['id']}/take/{edge}", headers=headers).json()  # hp 23
    pot = next(i for i in r["inventory"] if i["slug"] == "health_potion")
    r2 = client.post(f"/api/runs/{run['id']}/use-item/{pot['item_id']}", headers=headers).json()
    assert r2["snapshot"]["characters"][0]["hp"] == 28  # healed, capped at max
    assert not any(i["slug"] == "health_potion" for i in r2["inventory"])  # consumed


def test_restore_rewind(client, auth, campaign):
    headers, _ = auth()
    sid = campaign["story_id"]
    run = client.post(f"/api/stories/{sid}/runs", json={"char_class": "warrior"}, headers=headers).json()
    rid = run["id"]
    r = client.post(f"/api/runs/{rid}/take/{_choice(run, 'Step forward')['edge_id']}", headers=headers).json()
    if r["choices"]:
        r = client.post(f"/api/runs/{rid}/take/{r['choices'][0]['edge_id']}", headers=headers).json()
    summ = client.get(f"/api/runs/{rid}/summary", headers=headers).json()
    first = summ["journey"][0]
    back = client.post(f"/api/runs/{rid}/restore/{first['id']}", headers=headers).json()
    assert back["status"] == "active"
    assert back["snapshot"]["characters"][0]["hp"] == 23  # state after step 1


def test_item_requirement_gate(client, auth, db, campaign):
    """A lockpick-gated edge: locked without it, passes + consumes with it (rogue
    starts with one)."""
    from storybuilder import add_branch
    from models import Edge, EdgeOutcome, Requirement
    from sqlalchemy import select
    headers, _ = auth()
    sid = campaign["story_id"]
    gate_node = add_branch(db, story_id=sid, from_node_id=None, author_id=campaign["author_id"],
                           label="Pick the gate", content="click.")
    edge = db.scalar(select(Edge).join(EdgeOutcome, EdgeOutcome.edge_id == Edge.id)
                     .where(EdgeOutcome.to_node_id == gate_node))
    db.add(Requirement(edge_id=edge.id, type="item", key="lockpick", amount=1, consume=True))
    db.commit()

    # warrior: no lockpick -> locked + 409
    wrun = client.post(f"/api/stories/{sid}/runs", json={"char_class": "warrior"}, headers=headers).json()
    gate = _choice(wrun, "Pick the gate")
    assert gate["locked"] is True
    assert client.post(f"/api/runs/{wrun['id']}/take/{gate['edge_id']}", headers=headers).status_code == 409

    # rogue: has lockpick -> unlocked, passes, consumed
    rrun = client.post(f"/api/stories/{sid}/runs", json={"char_class": "rogue"}, headers=headers).json()
    gate = _choice(rrun, "Pick the gate")
    assert gate["locked"] is False
    r = client.post(f"/api/runs/{rrun['id']}/take/{gate['edge_id']}", headers=headers).json()
    assert not any(i["slug"] == "lockpick" for i in r["inventory"])
