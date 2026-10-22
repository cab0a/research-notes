# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'base_thickness': 5.8, 'height': 41.0, 'length': 49.0, 'wall_thickness': 4.0, 'width': 49.0}
OPENING='top'
SOURCE_SHA256='e0e2a422bb79438e33ea98012f09893954375668677b0569241ecdc68b41c5a3'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
