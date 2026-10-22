# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'width': 60.0, 'length': 40.0, 'thickness': 12.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'pocket_width': 20.0, 'pocket_length': 14.0, 'pocket_depth': 8.0}
OPENING='bottom'
SOURCE_SHA256='0a8d7a93de270b946ef7974437c03aab3b108af0c574f596cb159628b9719504'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
