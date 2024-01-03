
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple


@dataclass
class ShaderAggregate:
    shader: str
    flags: Set[int]
    textures: List[bool]
    material: Dict[str, Any]
    extra_properties: List[bool] # 16 bools, extra_properties[i] = True if for any attribset using this shader extra_properties[i] != 0
    vertex_format: Set[Tuple[int, int]]
    uses_matrices: Set[bool]