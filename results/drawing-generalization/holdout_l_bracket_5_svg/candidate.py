# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'width': 66.0, 'length': 35.0, 'height': 35.0, 'wall_thickness': 5.0, 'base_thickness': 5.6}
OPENING='top'
SOURCE_SHA256='47f49b3a78795108abb761c4c40349e6a40c34a3c8f9abc56781219ccb111542'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
