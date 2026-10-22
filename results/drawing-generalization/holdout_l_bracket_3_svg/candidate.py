# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'width': 44.0, 'length': 49.0, 'height': 38.0, 'wall_thickness': 4.0, 'base_thickness': 4.8}
OPENING='top'
SOURCE_SHA256='f3461c590aea739312ee580dcfc00943f94f0906486142ab2671b0f13c93f63e'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
