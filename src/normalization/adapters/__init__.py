"""Provider dispatch."""
from . import isolved, prismhr, ukg_ready

ADAPTERS = {"prismhr": prismhr, "isolved": isolved, "ukg-ready": ukg_ready}
ENTITIES = ("company", "employee", "direct-deposit", "payroll")
