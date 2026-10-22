# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 5.5, 'kind': 'pocket', 'length': 16.0, 'opening': 'top', 'width': 23.0, 'x': 12.0, 'y': 12.0}, {'diameter': 8.5, 'kind': 'hole', 'x': 67.5, 'y': 47.0}], 'length': 64.0, 'thickness': 15.0, 'width': 94.0}
SOURCE_SHA256='748de2ad22a988a0d7a419c482e36a6ab6d8bea38f6f28704ceb28dff4cc2374'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
