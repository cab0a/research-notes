# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'width': 58.0, 'length': 49.0, 'height': 37.0, 'wall_thickness': 3.5, 'base_thickness': 4.4}
OPENING='top'
SOURCE_SHA256='ae47ff4935dfc09e93329f3b7bdfb343231b95be5a506188ba60ce91d856d3e9'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
