# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'l_bracket'
PARAMETERS = {'width': 40.0, 'length': 30.0, 'height': 24.0, 'wall_thickness': 5.0, 'base_thickness': 5.0}
SOURCE_SHA256 = 'cd43b9503e80166e8d559166f3e1a3b6375c62572c467bfe02b1333142a55576'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
