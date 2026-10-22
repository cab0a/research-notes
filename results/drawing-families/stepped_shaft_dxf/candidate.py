# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'stepped_shaft'
PARAMETERS = {'length1': 24.0, 'length2': 16.0, 'diameter1': 16.0, 'diameter2': 10.0}
SOURCE_SHA256 = '34b71b8a4549301a2f3e1727892e9bc1008f2760c2e547c83b72f437762a12e8'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
