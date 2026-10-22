# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'diameter1': 22.0, 'diameter2': 10.4, 'length1': 37.0, 'length2': 16.0}
OPENING='top'
SOURCE_SHA256='be6b0abf25065b681258f37449bb2e3d18519ce870d14c179f5cb526c5a97205'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
