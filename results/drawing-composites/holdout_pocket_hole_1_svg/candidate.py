# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 118.0, 'length': 83.0, 'thickness': 19.0, 'features': [{'kind': 'pocket', 'x': 14.0, 'y': 12.0, 'width': 22.0, 'length': 16.0, 'depth': 5.5, 'opening': 'top'}, {'kind': 'hole', 'x': 95.0, 'y': 66.0, 'diameter': 8.0}]}
SOURCE_SHA256='e9e4c200fb9bda43eac89a95373d220dbd08bbcc6d0bc890d49fd875698a034b'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
