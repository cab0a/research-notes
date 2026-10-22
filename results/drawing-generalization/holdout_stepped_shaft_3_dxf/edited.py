# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='stepped_shaft'
PARAMETERS={'diameter1': 20.0, 'diameter2': 9.2, 'length1': 39.0, 'length2': 12.0}
OPENING='top'
SOURCE_SHA256='4ac340e27ac6b894f32df4da991a37b51718bf99320f05699dde6bcd1c3bf644'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
