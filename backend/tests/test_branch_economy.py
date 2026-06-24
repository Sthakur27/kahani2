import promotion


def test_create_at_cap_becomes_candidate(client, auth, db, campaign):
    """Root starts with 1 active ('Step forward'); fill to the cap of 3, then the
    next submission files as a candidate and stays out of the active list."""
    from storybuilder import add_branch
    headers, _ = auth()
    sid = campaign["story_id"]
    add_branch(db, story_id=sid, from_node_id=None, author_id=campaign["author_id"], label="B", content="b")
    add_branch(db, story_id=sid, from_node_id=None, author_id=campaign["author_id"], label="C", content="c")
    db.commit()

    r = client.post(f"/api/stories/{sid}/nodes",
                    json={"content": "a fourth opening", "edge_prompt": "D", "parent_node_id": None},
                    headers=headers)
    assert r.status_code == 201
    assert r.json()["edge_status"] == "candidate"
    nid = r.json()["id"]

    active = client.get(f"/api/stories/{sid}/nodes").json()
    candidate = client.get(f"/api/stories/{sid}/nodes?status=candidate").json()
    assert nid not in [n["id"] for n in active]
    assert nid in [n["id"] for n in candidate]


def test_promotion_unseats_weakest_unprotected(db, campaign):
    """A hub with 3 unprotected active leaves + a candidate voted above them:
    promotion seats the candidate and relegates the weakest active."""
    from storybuilder import add_branch
    from models import Story, StoryNode, Edge, EdgeOutcome, EdgeVote, User
    from sqlalchemy import select

    sid = campaign["story_id"]
    story = db.get(Story, sid)
    voter = db.scalar(select(User).where(User.username == "test_author"))
    hub = add_branch(db, story_id=sid, from_node_id=None, author_id=campaign["author_id"], label="hub", content="hub")
    db.commit()
    for lbl in ("A", "B", "C"):
        add_branch(db, story_id=sid, from_node_id=hub, author_id=campaign["author_id"], label=lbl, content=lbl)
    db.commit()

    # candidate edge D + node, voted +1 (beats the 0-score actives)
    e = Edge(story_id=sid, from_node_id=hub, label="D", kind="plain", status="candidate",
             created_by=campaign["author_id"])
    db.add(e)
    db.flush()
    dn = StoryNode(story_id=sid, parent_node_id=hub, user_id=campaign["author_id"],
                   edge_prompt="D", content="d")
    db.add(dn)
    db.flush()
    db.add(EdgeOutcome(edge_id=e.id, band="plain", to_node_id=dn.id))
    db.add(EdgeVote(user_id=voter.id, story_node_id=dn.id, value=1))
    db.commit()

    changes = promotion.promote_choice_point(db, story, hub)
    assert changes == 1
    active_labels = {x.label for x in db.scalars(
        select(Edge).where(Edge.from_node_id == hub, Edge.status == "active"))}
    assert "D" in active_labels
    assert len(active_labels) == 3  # one of A/B/C relegated
