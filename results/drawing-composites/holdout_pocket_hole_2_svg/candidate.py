# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 113.0, 'length': 81.0, 'thickness': 21.0, 'features': [{'kind': 'pocket', 'x': 15.0, 'y': 12.0, 'width': 22.0, 'length': 17.0, 'depth': 6.0, 'opening': 'top'}, {'kind': 'hole', 'x': 89.0, 'y': 63.0, 'diameter': 8.5}]}
SOURCE_SHA256='a6f85010a1e68b4eccfa2e9a9c90c689a0447a72beb1a2061e3c9def95b0bd6f'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
