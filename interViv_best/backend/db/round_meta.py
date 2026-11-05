"""Server-only round metadata keys.

These keys have no dedicated column. The SQL store round-trips them through
``rounds.private_meta_json``; the memory store keeps them on the document.
``sanitize_round_for_client`` strips them from every client payload.
"""

from __future__ import annotations

ROUND_PRIVATE_META_KEYS: tuple[str, ...] = (
    "coding_exec_count",
    "follow_up_scoring",
    "purpose",
    "wpm",
    "pause_count",
    # Slice 1: who scheduled a follow-up and why (system follow-ups only).
    "follow_up_initiator",
    "follow_up_kind",
)

# Written into ``config_json`` before revision 20261103_0017; read back as a
# fallback so legacy SQL rows keep their follow-up review status.
LEGACY_CONFIG_META_KEYS: tuple[str, ...] = ("follow_up_scoring",)
