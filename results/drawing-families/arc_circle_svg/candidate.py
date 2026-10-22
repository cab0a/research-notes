# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'width': 46.0, 'length': 34.0, 'thickness': 7.0, 'holes': [{'x': 13.0, 'y': 11.0, 'diameter': 5.0}]}
SOURCE_SHA256 = '2d413588db0d5c44348ceb58ccf28bfcb6665b55b9d333d9a94fe25adc0f1ccc'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
