# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'diameter1': 23.0, 'diameter2': 11.0, 'length1': 33.0, 'length2': 23.0}
OPENING='top'
SOURCE_SHA256='6095a9fd20c49e06bfe963cdd095f780bf4e548699ee10011e2a97aa1bd2f3f0'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
