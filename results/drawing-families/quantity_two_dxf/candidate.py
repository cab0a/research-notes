# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'width': 54.0, 'length': 40.0, 'thickness': 8.0, 'holes': [{'x': 12.0, 'y': 10.0, 'diameter': 6.0}, {'x': 38.0, 'y': 28.0, 'diameter': 6.0}]}
SOURCE_SHA256 = '03920b68b768bb8b8a75c5329091b26d60a7d68b00f87c89c3170d4b076f3d2c'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
