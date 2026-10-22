# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'width': 45.0, 'length': 40.0, 'height': 33.0, 'wall_thickness': 5.5, 'base_thickness': 6.0}
OPENING='top'
SOURCE_SHA256='8580e56db37f2bca9869f6be1dc8a0c8646e8112ed8664be2c0a0c19109733ac'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
