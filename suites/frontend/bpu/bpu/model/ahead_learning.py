"""Two real control-flow edges, then a changed indirect destination."""
PC=0x40000800
OTHER=PC+0x226
NEW_TARGET=PC+0x648
EDGES={PC:(4,OTHER),OTHER:(9,PC)}
