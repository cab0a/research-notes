# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 112.0, 'length': 78.0, 'thickness': 21.0, 'features': [{'kind': 'step', 'x': 0.0, 'y': 0.0, 'width': 29.0, 'length': 21.0, 'depth': 7.0, 'opening': 'top'}, {'kind': 'hole', 'x': 88.0, 'y': 59.0, 'diameter': 8.5}]}
SOURCE_SHA256='184d4698c54d7c01001ebb2e96edddcfbe13f99cb638336376a1fd151cc11ab5'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
