# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'holes': [{'diameter': 9.0, 'x': 21.0, 'y': 14.0}], 'length': 42.0, 'thickness': 12.0, 'width': 65.0}
SOURCE_SHA256 = '25d3040c5fe5d28f4a0cc147a7cb18f9c284474cc0f9c0a523b808e82bb7ddc1'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
