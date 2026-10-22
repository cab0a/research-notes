# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'length': 40.0, 'pocket_depth': 5.0, 'pocket_length': 14.0, 'pocket_width': 22.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'thickness': 12.0, 'width': 65.0}
OPENING='top'
SOURCE_SHA256='bd0c9af2e4d5da9bc34e7e5a7b1c9dd38ed3212971ead5f23605d1edd399c37f'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
