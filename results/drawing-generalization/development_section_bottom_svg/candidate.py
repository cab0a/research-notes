# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'width': 60.0, 'length': 40.0, 'thickness': 12.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'pocket_width': 20.0, 'pocket_length': 14.0, 'pocket_depth': 8.0}
OPENING='bottom'
SOURCE_SHA256='57b572e241b73bb69201351c6e91e761cdd5f23efc873d6a609d1b746d1827b9'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
