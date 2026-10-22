# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'length1': 29.0, 'length2': 23.0, 'diameter1': 23.0, 'diameter2': 10.0}
OPENING='top'
SOURCE_SHA256='4f2040b1366f87aed9caf44cd536f7e9b5e864dc164ee06d3ce3b2041dce0442'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
