# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 6.0, 'kind': 'pocket', 'length': 16.0, 'opening': 'top', 'width': 23.0, 'x': 14.0, 'y': 12.0}, {'diameter': 8.5, 'kind': 'hole', 'x': 95.5, 'y': 66.0}], 'length': 83.0, 'thickness': 20.0, 'width': 122.0}
SOURCE_SHA256='e9e4c200fb9bda43eac89a95373d220dbd08bbcc6d0bc890d49fd875698a034b'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
