# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 6.5, 'kind': 'pocket', 'length': 17.0, 'opening': 'top', 'width': 23.0, 'x': 15.0, 'y': 12.0}, {'diameter': 9.0, 'kind': 'hole', 'x': 89.5, 'y': 63.0}], 'length': 81.0, 'thickness': 22.0, 'width': 117.0}
SOURCE_SHA256='a6f85010a1e68b4eccfa2e9a9c90c689a0447a72beb1a2061e3c9def95b0bd6f'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
