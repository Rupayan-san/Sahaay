from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import imagehash
from PIL import Image

HASH_SIZE = 16
HASH_BITS = HASH_SIZE * HASH_SIZE


@dataclass(frozen=True, slots=True)
class HashBundle:
    phash: str
    dhash: str
    whash: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "HashBundle":
        return cls(
            phash=str(payload["phash"]),
            dhash=str(payload["dhash"]),
            whash=str(payload["whash"]),
        )


def compute_hash_bundle(image: Image.Image) -> HashBundle:
    rgb_image = image.convert("RGB")
    return HashBundle(
        phash=str(imagehash.phash(rgb_image, hash_size=HASH_SIZE)),
        dhash=str(imagehash.dhash(rgb_image, hash_size=HASH_SIZE)),
        whash=str(imagehash.whash(rgb_image, hash_size=HASH_SIZE)),
    )


def hash_bundle_similarity(left: HashBundle, right: HashBundle) -> float:
    similarities = [
        _single_hash_similarity(left.phash, right.phash),
        _single_hash_similarity(left.dhash, right.dhash),
        _single_hash_similarity(left.whash, right.whash),
    ]
    return sum(similarities) / len(similarities)


def _single_hash_similarity(left_hash: str, right_hash: str) -> float:
    left = imagehash.hex_to_hash(left_hash)
    right = imagehash.hex_to_hash(right_hash)
    distance = left - right
    return max(0.0, 1.0 - (distance / HASH_BITS))
