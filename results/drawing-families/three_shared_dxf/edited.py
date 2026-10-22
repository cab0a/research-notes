# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'holes': [{'diameter': 7.0, 'x': 13.0, 'y': 10.0}, {'diameter': 6.0, 'x': 12.0, 'y': 28.0}, {'diameter': 6.0, 'x': 38.0, 'y': 20.0}], 'length': 40.0, 'thickness': 10.0, 'width': 59.0}
SOURCE_SHA256 = '216aee7eb919987d05c4075d48fbe2c59d0bb3d4ccd414c4b07551b4903aa504'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
