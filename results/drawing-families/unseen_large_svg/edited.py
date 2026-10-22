# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'holes': [{'diameter': 9.0, 'x': 21.0, 'y': 14.0}], 'length': 42.0, 'thickness': 12.0, 'width': 65.0}
SOURCE_SHA256 = 'f949066951678325211d7ae70f1bda4fae26598828112c4002ba90bce9d16a85'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
