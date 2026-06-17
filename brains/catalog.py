"""Catalog of available brains, keyed by ``brain_id``.

This is the single place that maps a brain id to its class. The standalone
brain runner and bootstrap use it so brains stay plug-and-play: register a new
brain here and it can be launched in-process or in its own container.
"""

from __future__ import annotations

from brains._base.brain import BaseBrain
from brains.capital import CapitalBrain
from brains.ckos import CKOSBrain
from brains.commander import CommanderBrain
from brains.venture import VentureBrain

BRAIN_CLASSES: dict[str, type[BaseBrain]] = {
    CKOSBrain.brain_id: CKOSBrain,
    VentureBrain.brain_id: VentureBrain,
    CommanderBrain.brain_id: CommanderBrain,
    CapitalBrain.brain_id: CapitalBrain,
}


def get_brain_class(brain_id: str) -> type[BaseBrain]:
    """Return the brain class registered for ``brain_id``.

    Args:
        brain_id: The brain identifier.

    Returns:
        The brain class.

    Raises:
        KeyError: If no brain is registered under that id.
    """
    if brain_id not in BRAIN_CLASSES:
        raise KeyError(
            f"Unknown brain '{brain_id}'. Known brains: {sorted(BRAIN_CLASSES)}"
        )
    return BRAIN_CLASSES[brain_id]
