# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 122.0, 'length': 79.0, 'thickness': 23.0, 'features': [{'kind': 'step', 'x': 0.0, 'y': 0.0, 'width': 30.0, 'length': 22.0, 'depth': 7.5, 'opening': 'top'}, {'kind': 'hole', 'x': 97.0, 'y': 59.0, 'diameter': 9.0}]}
SOURCE_SHA256='ab9f6104de0e4faf0a54901b3718cfc2cb49a40b4169fd21cad6bca56b808d70'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
