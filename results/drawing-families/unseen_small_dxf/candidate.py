# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'width': 46.0, 'length': 34.0, 'thickness': 7.0, 'holes': [{'x': 13.0, 'y': 11.0, 'diameter': 5.0}]}
SOURCE_SHA256 = '18ab8487b5ee499a30029dd25ce81080d374df03b45db0f20218f74ec98314a7'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
