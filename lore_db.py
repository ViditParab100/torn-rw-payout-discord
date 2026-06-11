"""
ChromaDB semantic layer for player lore.

MongoDB is the source of truth. This module provides an in-memory vector index
rebuilt from MongoDB at startup, enabling semantic queries like:
  "who is leader of KOWR" → ChineseGandalf
  "who works as a mechanic" → JNRanger / Jeremy
  "who joined recently" → finds relevant lore bits

Architecture:
- One document per lore fact, with player name as metadata
- Cosine similarity space for better semantic matching
- Rebuilt entirely from MongoDB on startup (no disk persistence needed)
- Static faction facts pre-seeded so Jeremy always knows key roles
"""

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
import hashlib

import memory_db

_client = chromadb.EphemeralClient()
_ef = DefaultEmbeddingFunction()
_col = _client.get_or_create_collection(
    name="player_lore",
    embedding_function=_ef,
    metadata={"hnsw:space": "cosine"}
)

# Hard-coded faction facts — always searchable regardless of conversation history
STATIC_FACTS = {
    "ChineseGandalf": [
        "ChineseGandalf is the Leader of KnockOut WeightRoom (KOWR)",
        "ChineseGandalf runs the faction, he is the faction leader",
        "The faction leader is ChineseGandalf",
        "ChineseGandalf is in charge of KOWR",
    ],
    "Xtatik": [
        "Xtatik is the Co-Leader of KnockOut WeightRoom (KOWR)",
        "Xtatik is second in command of the faction, the co-leader",
        "Xtatik handles leadership alongside ChineseGandalf",
        "The co-leader of KOWR is Xtatik",
    ],
    "JNRanger": [
        "JNRanger is the in-game name of CyberJeremy, a late faction member",
        "JNRanger was a mechanic and welder from North Brampton, Ontario",
        "JNRanger fought in wars 21076, 22195, and 24604 for KnockOut WeightRoom",
        "JNRanger personal best: 104 hits in War 24604 vs The Mile High Clinic",
    ],
    "Stumptronic": [
        "Stumptronic is the Leader of KnockOut RingSide, the sister faction to KOWR",
        "The sister faction KnockOut RingSide is led by Stumptronic",
    ],
    "KOWR": [
        "KOWR stands for KnockOut WeightRoom, faction tag KOWR, ID 43889",
        "KnockOut WeightRoom sister faction is KnockOut RingSide",
        "KnockOut WeightRoom is led by ChineseGandalf with Xtatik as co-leader",
    ],
    "Star_vader": [
        "Star_vader created CyberJeremy as a digital tribute to JNRanger",
        "Star_vader is from Mumbai, India",
        "Star_vader is one of the bot creators for KnockOut WeightRoom",
        "Star_vader lives in Bangalore",
    ],
    "Spidernnam": [
        "Spidernnam left KnockOut WeightRoom to join a reviver faction for revive training",
        "Spidernnam left the faction and is no longer a member of KOWR",
        "Spidernnam departed to a reviver faction to train his reviving skill",
        "Spidernnam used to be in KOWR but left to train as a reviver in a dedicated reviver faction",
    ],
}


def _make_id(player: str, fact: str) -> str:
    return hashlib.md5(f"{player.lower()}|{fact}".encode()).hexdigest()


def index_player_lore(player_name: str, fact: str):
    """Upsert a single lore fact into the vector index."""
    try:
        _col.upsert(
            documents=[fact],
            metadatas=[{"player": player_name}],
            ids=[_make_id(player_name, fact)]
        )
    except Exception as e:
        print(f"[LoreDB] index error for {player_name}: {e}")


def search_who(query: str, n_results: int = 5, distance_threshold: float = 0.7) -> list:
    """
    Semantic search across all indexed player facts.
    Returns [{player, fact, distance}] sorted by relevance (lower distance = better).
    Only returns results below distance_threshold to filter noise.
    """
    count = _col.count()
    if count == 0:
        return []
    try:
        res = _col.query(
            query_texts=[query],
            n_results=min(n_results, count),
            include=["documents", "metadatas", "distances"]
        )
        out = []
        for doc, meta, dist in zip(
            res["documents"][0],
            res["metadatas"][0],
            res["distances"][0]
        ):
            if dist <= distance_threshold:
                out.append({"player": meta["player"], "fact": doc, "distance": dist})
        return out
    except Exception as e:
        print(f"[LoreDB] search error: {e}")
        return []


def rebuild_from_mongodb():
    """
    Populate the in-memory index from MongoDB lore + static faction facts.
    Call once at bot startup.
    """
    # Static facts first
    for player, facts in STATIC_FACTS.items():
        for fact in facts:
            index_player_lore(player, fact)

    # MongoDB lore
    all_docs = list(memory_db.lore_col.find({}))
    count = 0
    for doc in all_docs:
        player = doc.get("username_display") or doc.get("username", "?")
        for fact in doc.get("lore_bits", []):
            index_player_lore(player, fact)
            count += 1

    static_count = sum(len(v) for v in STATIC_FACTS.values())
    print(f"[LoreDB] Indexed {count} MongoDB facts + {static_count} static facts "
          f"for {len(all_docs)} players.")
