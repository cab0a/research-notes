# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'width': 60.0, 'length': 42.0, 'thickness': 10.0, 'holes': [{'x': 20.0, 'y': 14.0, 'diameter': 8.0}]}
SOURCE_SHA256 = 'f949066951678325211d7ae70f1bda4fae26598828112c4002ba90bce9d16a85'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
