# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'diameter1': 19.0, 'diameter2': 8.6, 'length1': 37.0, 'length2': 17.0}
OPENING='top'
SOURCE_SHA256='ddccb7e04ecb9180973db44c9782c6c710ed219743281de12fc9229d74c4e61b'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
