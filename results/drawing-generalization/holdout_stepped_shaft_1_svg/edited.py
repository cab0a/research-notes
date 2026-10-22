# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'diameter1': 18.0, 'diameter2': 8.0, 'length1': 47.0, 'length2': 18.0}
OPENING='top'
SOURCE_SHA256='1cfcbb67e43ba3e276436ec0423c7182b2ab9af76db498e47d9b31a37463dcb9'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
