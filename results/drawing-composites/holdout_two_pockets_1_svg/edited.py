# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 6.0, 'kind': 'pocket', 'length': 15.0, 'opening': 'top', 'width': 23.0, 'x': 10.0, 'y': 12.0}, {'depth': 8.5, 'kind': 'pocket', 'length': 18.0, 'opening': 'top', 'width': 24.0, 'x': 75.0, 'y': 53.0}], 'length': 82.0, 'thickness': 20.0, 'width': 123.0}
SOURCE_SHA256='89981586e7d0dfda27242945c9c933a4196c8750f9078ddb77e0dde6b57f788a'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
