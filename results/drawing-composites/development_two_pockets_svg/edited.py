# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 5.5, 'kind': 'pocket', 'length': 15.0, 'opening': 'top', 'width': 21.0, 'x': 10.0, 'y': 12.0}, {'depth': 8.0, 'kind': 'pocket', 'length': 18.0, 'opening': 'top', 'width': 24.0, 'x': 64.0, 'y': 43.0}], 'length': 72.0, 'thickness': 19.0, 'width': 112.0}
SOURCE_SHA256='a4c2e72f38d6621ade5ce8c9ad58d12177e64d694f5ef8b00fdbb7740670d3cf'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
