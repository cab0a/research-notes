# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'diameter1': 21.0, 'diameter2': 9.8, 'length1': 47.0, 'length2': 12.0}
OPENING='top'
SOURCE_SHA256='278b9ecb5f2c279642cac4e5b071c290d6bfadc0593326715348900e7bb1b6a0'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
