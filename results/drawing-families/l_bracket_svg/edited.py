# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'l_bracket'
PARAMETERS = {'base_thickness': 6.0, 'height': 27.0, 'length': 30.0, 'wall_thickness': 5.0, 'width': 45.0}
SOURCE_SHA256 = 'bfea178400212476794e999031ed7a06c3cde33a44b7e9eb73159e46227d269a'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
