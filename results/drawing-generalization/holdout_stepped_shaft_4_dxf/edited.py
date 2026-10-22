# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'diameter1': 21.0, 'diameter2': 9.8, 'length1': 47.0, 'length2': 12.0}
OPENING='top'
SOURCE_SHA256='0e5d8d1fa91ce723b6a9996c69f11c0e123be605109eda6923a30c49cb859a9c'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
