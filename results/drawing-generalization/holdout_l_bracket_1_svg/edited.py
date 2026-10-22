# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'base_thickness': 5.0, 'height': 38.0, 'length': 42.0, 'wall_thickness': 3.0, 'width': 66.0}
OPENING='top'
SOURCE_SHA256='1b63727bd0a66899de2114afdae09ae46067b157cf4032f5cdf465b2a9b74a71'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
