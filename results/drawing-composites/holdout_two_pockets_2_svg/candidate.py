# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'width': 118.0, 'length': 78.0, 'thickness': 21.0, 'features': [{'kind': 'pocket', 'x': 10.0, 'y': 12.0, 'width': 23.0, 'length': 16.0, 'depth': 6.0, 'opening': 'top'}, {'kind': 'pocket', 'x': 74.0, 'y': 49.0, 'width': 24.0, 'length': 19.0, 'depth': 9.0, 'opening': 'top'}]}
SOURCE_SHA256='2b9871b5018f0ed3da39689de699cb7f912893d547480fb9e6a7c62e5bfd211b'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
