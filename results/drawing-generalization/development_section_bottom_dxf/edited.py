# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'length': 40.0, 'pocket_depth': 9.0, 'pocket_length': 14.0, 'pocket_width': 22.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'thickness': 12.0, 'width': 65.0}
OPENING='bottom'
SOURCE_SHA256='8342bac6783261267314866092b9e48773312a17ea97fb37d6ef985fc024060e'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
