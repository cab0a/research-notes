# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 7.0, 'kind': 'step', 'length': 20.0, 'opening': 'top', 'width': 29.0, 'x': 0.0, 'y': 0.0}, {'diameter': 8.5, 'kind': 'hole', 'x': 106.5, 'y': 59.0}], 'length': 77.0, 'thickness': 20.0, 'width': 133.0}
SOURCE_SHA256='d637e73243179b9df65c3187aa2ec72bda00cb7f7124921beedb4d67e589e647'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
