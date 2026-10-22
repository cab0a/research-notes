# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 90.0, 'length': 64.0, 'thickness': 16.0, 'features': [{'kind': 'step', 'x': 0.0, 'y': 0.0, 'width': 26.0, 'length': 20.0, 'depth': 6.0, 'opening': 'top'}, {'kind': 'hole', 'x': 67.0, 'y': 46.0, 'diameter': 8.0}]}
SOURCE_SHA256='ef42750975893c1dd21da2c08163145ba47dbc8229446d9a9c79d84522620b5b'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
