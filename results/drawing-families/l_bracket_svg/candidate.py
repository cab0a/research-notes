# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'l_bracket'
PARAMETERS = {'width': 40.0, 'length': 30.0, 'height': 24.0, 'wall_thickness': 5.0, 'base_thickness': 5.0}
SOURCE_SHA256 = 'bfea178400212476794e999031ed7a06c3cde33a44b7e9eb73159e46227d269a'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
