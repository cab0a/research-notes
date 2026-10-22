# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 90.0, 'length': 64.0, 'thickness': 14.0, 'features': [{'kind': 'pocket', 'x': 12.0, 'y': 12.0, 'width': 22.0, 'length': 16.0, 'depth': 5.0, 'opening': 'top'}, {'kind': 'hole', 'x': 67.0, 'y': 47.0, 'diameter': 8.0}]}
SOURCE_SHA256='748de2ad22a988a0d7a419c482e36a6ab6d8bea38f6f28704ceb28dff4cc2374'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
