# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'length': 40.0, 'pocket_depth': 5.0, 'pocket_length': 14.0, 'pocket_width': 22.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'thickness': 12.0, 'width': 65.0}
OPENING='top'
SOURCE_SHA256='591b08e639674fbb00c61b856dedbb6da814abaa2f095eee258b57f688b819b5'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
