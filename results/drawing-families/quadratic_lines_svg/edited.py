# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'holes': [{'diameter': 6.0, 'x': 14.0, 'y': 11.0}], 'length': 34.0, 'thickness': 9.0, 'width': 51.0}
SOURCE_SHA256 = '3879b86bf7bb579657cc1e7e6886cfae3e8c91b9d7ab367b126d9976b307c3fe'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
