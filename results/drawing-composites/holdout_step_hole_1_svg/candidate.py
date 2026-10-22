# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 129.0, 'length': 77.0, 'thickness': 19.0, 'features': [{'kind': 'step', 'x': 0.0, 'y': 0.0, 'width': 28.0, 'length': 20.0, 'depth': 6.5, 'opening': 'top'}, {'kind': 'hole', 'x': 106.0, 'y': 59.0, 'diameter': 8.0}]}
SOURCE_SHA256='d637e73243179b9df65c3187aa2ec72bda00cb7f7124921beedb4d67e589e647'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
