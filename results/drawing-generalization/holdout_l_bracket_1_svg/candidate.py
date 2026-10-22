# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'width': 61.0, 'length': 42.0, 'height': 35.0, 'wall_thickness': 3.0, 'base_thickness': 4.0}
OPENING='top'
SOURCE_SHA256='1b63727bd0a66899de2114afdae09ae46067b157cf4032f5cdf465b2a9b74a71'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
