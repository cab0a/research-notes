# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'length': 62.0, 'pocket_depth': 5.5, 'pocket_length': 13.0, 'pocket_width': 21.0, 'pocket_x': 10.5, 'pocket_y': 8.5, 'thickness': 15.0, 'width': 89.0}
OPENING='bottom'
SOURCE_SHA256='920408237f8750efcbd594650588d91df330f63be69dec0b9a9c3aee019290cc'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
