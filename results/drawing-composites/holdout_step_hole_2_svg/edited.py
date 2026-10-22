# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 7.5, 'kind': 'step', 'length': 21.0, 'opening': 'top', 'width': 30.0, 'x': 0.0, 'y': 0.0}, {'diameter': 9.0, 'kind': 'hole', 'x': 88.5, 'y': 59.0}], 'length': 78.0, 'thickness': 22.0, 'width': 116.0}
SOURCE_SHA256='184d4698c54d7c01001ebb2e96edddcfbe13f99cb638336376a1fd151cc11ab5'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
