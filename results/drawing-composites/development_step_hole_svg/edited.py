# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 6.5, 'kind': 'step', 'length': 20.0, 'opening': 'top', 'width': 27.0, 'x': 0.0, 'y': 0.0}, {'diameter': 8.5, 'kind': 'hole', 'x': 67.5, 'y': 46.0}], 'length': 64.0, 'thickness': 17.0, 'width': 94.0}
SOURCE_SHA256='ef42750975893c1dd21da2c08163145ba47dbc8229446d9a9c79d84522620b5b'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
