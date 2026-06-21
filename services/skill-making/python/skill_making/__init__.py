"""Tapestry skill-making bridge — Step 4 Refactor lift of Make_Skills/services/skill_making/.

Adds the sibling engine/skill-compiler package dir to sys.path so `skill_compiler`
(the compiler, lifted to engine/skill-compiler/python/) resolves from here.
parents: [0]=skill_making [1]=python [2]=skill-making [3]=services [4]=tapestry root.
"""
import sys
from pathlib import Path

_COMPILER_PKG = Path(__file__).resolve().parents[4] / "engine" / "skill-compiler" / "python"
if str(_COMPILER_PKG) not in sys.path:
    sys.path.insert(0, str(_COMPILER_PKG))
