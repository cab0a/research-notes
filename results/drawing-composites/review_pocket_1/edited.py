# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 5.0, 'kind': 'pocket', 'length': 12.0, 'opening': 'top', 'width': 20.0, 'x': 10.0, 'y': 8.0}], 'length': 60.0, 'thickness': 14.0, 'width': 86.0}
SOURCE_SHA256='62a275fa0ab098bb96e4c897d0a04de7a4facd1e046cd6d53e17ab558e68aa69'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
