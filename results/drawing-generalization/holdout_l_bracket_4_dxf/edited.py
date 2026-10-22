# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'base_thickness': 6.2, 'height': 43.0, 'length': 35.0, 'wall_thickness': 4.5, 'width': 48.0}
OPENING='top'
SOURCE_SHA256='f01bbb83f07b2bc00d0b261b629109b5ead5a8f3ce9b0e5885f83b12068928eb'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
