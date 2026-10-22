# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'holes': [{'diameter': 6.0, 'x': 14.0, 'y': 11.0}], 'length': 34.0, 'thickness': 9.0, 'width': 51.0}
SOURCE_SHA256 = 'b7127bd9f69f8146caee05452b4e2755ec15e3ec9ecc94e3cf4e338340623ef4'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
