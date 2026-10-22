# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 75.0, 'length': 60.0, 'thickness': 17.0, 'features': [{'kind': 'pocket', 'x': 11.5, 'y': 9.5, 'width': 21.0, 'length': 15.0, 'depth': 5.5, 'opening': 'bottom'}]}
SOURCE_SHA256='f9352b56fb9c06d805e05cb6ba2f73f5bd8d399c36b74c8517e8b3a01159bb2b'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
