# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'length1': 43.0, 'length2': 18.0, 'diameter1': 18.0, 'diameter2': 7.0}
OPENING='top'
SOURCE_SHA256='2645d2d2319123b862346c7102d042a7bbc244e1bae1e8f7f5cec5872aa59cc1'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
