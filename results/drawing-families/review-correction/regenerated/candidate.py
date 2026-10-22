# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'width': 46.0, 'length': 34.0, 'thickness': 7.0, 'holes': [{'x': 13.0, 'y': 11.0, 'diameter': 5.0}]}
SOURCE_SHA256 = '49fec39a9bc0bf7b60465eaa64f75559dfd099b95dcf0acdd0fcb8098aab1c49'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
