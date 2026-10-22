# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'holes': [{'diameter': 6.0, 'x': 14.0, 'y': 11.0}], 'length': 34.0, 'thickness': 9.0, 'width': 51.0}
SOURCE_SHA256 = 'd7103189f84e6558d6eb7c348107a6315ce849d5e20d99cb9d726cb4b8974fe9'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
