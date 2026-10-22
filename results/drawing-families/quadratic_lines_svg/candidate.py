# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'width': 46.0, 'length': 34.0, 'thickness': 7.0, 'holes': [{'x': 13.0, 'y': 11.0, 'diameter': 5.0}]}
SOURCE_SHA256 = '3879b86bf7bb579657cc1e7e6886cfae3e8c91b9d7ab367b126d9976b307c3fe'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
