# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'holes': [{'diameter': 7.0, 'x': 13.0, 'y': 10.0}, {'diameter': 8.0, 'x': 38.0, 'y': 28.0}], 'length': 40.0, 'thickness': 10.0, 'width': 59.0}
SOURCE_SHA256 = 'c23d443cdd7b7cbe9e01c466f6deb98038f24a4553cf943d2a97ceaa8e4571e9'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
