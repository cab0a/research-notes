# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'width': 60.0, 'length': 40.0, 'thickness': 12.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'pocket_width': 20.0, 'pocket_length': 14.0, 'pocket_depth': 4.0}
OPENING='top'
SOURCE_SHA256='afd340ba8e0cc68bc0ae3fa9e3b27514828e147baed9c37427a17f0435c724a6'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
