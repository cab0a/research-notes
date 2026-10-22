# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 119.0, 'length': 82.0, 'thickness': 19.0, 'features': [{'kind': 'pocket', 'x': 10.0, 'y': 12.0, 'width': 22.0, 'length': 15.0, 'depth': 5.5, 'opening': 'top'}, {'kind': 'pocket', 'x': 75.0, 'y': 53.0, 'width': 24.0, 'length': 18.0, 'depth': 8.5, 'opening': 'top'}]}
SOURCE_SHA256='89981586e7d0dfda27242945c9c933a4196c8750f9078ddb77e0dde6b57f788a'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
