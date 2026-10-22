# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'width': 45.0, 'length': 40.0, 'height': 33.0, 'wall_thickness': 5.5, 'base_thickness': 6.0}
OPENING='top'
SOURCE_SHA256='94af13768606ac6a636ad29e1fdd2f40dd465c3e48f5a37c2f64d0a28ab496c2'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
