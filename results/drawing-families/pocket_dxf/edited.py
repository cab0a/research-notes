# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'pocket'
PARAMETERS = {'length': 40.0, 'pocket_depth': 5.0, 'pocket_length': 14.0, 'pocket_width': 22.0, 'pocket_x': 12.0, 'pocket_y': 10.0, 'thickness': 12.0, 'width': 65.0}
SOURCE_SHA256 = '591b08e639674fbb00c61b856dedbb6da814abaa2f095eee258b57f688b819b5'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])
