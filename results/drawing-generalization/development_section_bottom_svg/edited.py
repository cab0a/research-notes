# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'length': 40.0, 'pocket_depth': 9.0, 'pocket_length': 14.0, 'pocket_width': 22.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'thickness': 12.0, 'width': 65.0}
OPENING='bottom'
SOURCE_SHA256='57b572e241b73bb69201351c6e91e761cdd5f23efc873d6a609d1b746d1827b9'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
