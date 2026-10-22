# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 8.0, 'kind': 'step', 'length': 22.0, 'opening': 'top', 'width': 31.0, 'x': 0.0, 'y': 0.0}, {'diameter': 9.5, 'kind': 'hole', 'x': 97.5, 'y': 59.0}], 'length': 79.0, 'thickness': 24.0, 'width': 126.0}
SOURCE_SHA256='ab9f6104de0e4faf0a54901b3718cfc2cb49a40b4169fd21cad6bca56b808d70'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
