def test_list_stories_has_total_header(client):
    r = client.get("/api/stories?limit=2")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert "X-Total-Count" in r.headers


def test_story_404(client):
    assert client.get("/api/stories/999999").status_code == 404


def test_story_exposes_mode(client, campaign):
    r = client.get(f"/api/stories/{campaign['story_id']}")
    assert r.status_code == 200
    assert r.json()["mode"] == "campaign"


def test_create_node_requires_auth(client, campaign):
    r = client.post(f"/api/stories/{campaign['story_id']}/nodes", json={"content": "x"})
    assert r.status_code == 401


def test_create_node_writes_edge_and_reads_back(client, auth, campaign):
    headers, _ = auth()
    sid = campaign["story_id"]
    r = client.post(
        f"/api/stories/{sid}/nodes",
        json={"content": "A fresh branch.", "edge_prompt": "Go left",
              "parent_node_id": campaign["node_a"]},
        headers=headers,
    )
    assert r.status_code == 201
    nid = r.json()["id"]
    assert r.json()["edge_status"] in ("active", "candidate")
    kids = client.get(f"/api/stories/{sid}/nodes?parent_id={campaign['node_a']}").json()
    assert nid in [n["id"] for n in kids]


def test_node_and_path(client, auth, campaign):
    headers, _ = auth()
    sid, a = campaign["story_id"], campaign["node_a"]
    node = client.get(f"/api/nodes/{a}", headers=headers).json()
    assert "children" in node
    path = client.get(f"/api/nodes/{a}/path").json()
    assert path[-1]["id"] == a


def test_moderation_blocks_pg_profanity(client, auth, campaign):
    headers, _ = auth()
    r = client.post(
        f"/api/stories/{campaign['story_id']}/nodes",
        json={"content": "what the hell is this damn place"},
        headers=headers,
    )
    assert r.status_code == 422
    assert r.json().get("moderation") is True
