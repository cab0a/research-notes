# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'base_thickness': 6.2, 'height': 43.0, 'length': 35.0, 'wall_thickness': 4.5, 'width': 48.0}
OPENING='top'
SOURCE_SHA256='4495470bf2f27c5b61bbaa02633902cd71d1f99d4120b3e40b95d29ca390c629'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
