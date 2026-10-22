# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'width': 43.0, 'length': 35.0, 'height': 40.0, 'wall_thickness': 4.5, 'base_thickness': 5.2}
OPENING='top'
SOURCE_SHA256='f01bbb83f07b2bc00d0b261b629109b5ead5a8f3ce9b0e5885f83b12068928eb'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
