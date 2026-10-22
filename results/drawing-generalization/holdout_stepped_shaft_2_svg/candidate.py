# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'length1': 33.0, 'length2': 17.0, 'diameter1': 19.0, 'diameter2': 7.6}
OPENING='top'
SOURCE_SHA256='3445ee4763c03271be25812dfa5831f2d3f852232a1a905e1db966b4c94cc9fd'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
