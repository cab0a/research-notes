# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'width': 60.0, 'length': 40.0, 'thickness': 12.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'pocket_width': 20.0, 'pocket_length': 14.0, 'pocket_depth': 4.0}
OPENING='top'
SOURCE_SHA256='591b08e639674fbb00c61b856dedbb6da814abaa2f095eee258b57f688b819b5'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
