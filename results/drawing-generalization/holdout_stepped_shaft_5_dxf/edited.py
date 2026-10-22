# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'diameter1': 22.0, 'diameter2': 10.4, 'length1': 37.0, 'length2': 16.0}
OPENING='top'
SOURCE_SHA256='c461fb8961f35612bd036625d7f1432e1babad484c7baa40659d2588b5f23c68'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
