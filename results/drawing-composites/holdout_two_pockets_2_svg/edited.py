# Editable reconstructed cuts; not recovered authoring history.
from research_notes.drawing_composites import export
PARAMETERS={'features': [{'depth': 6.5, 'kind': 'pocket', 'length': 16.0, 'opening': 'top', 'width': 24.0, 'x': 10.0, 'y': 12.0}, {'depth': 9.0, 'kind': 'pocket', 'length': 19.0, 'opening': 'top', 'width': 24.0, 'x': 74.0, 'y': 49.0}], 'length': 78.0, 'thickness': 22.0, 'width': 122.0}
SOURCE_SHA256='2b9871b5018f0ed3da39689de699cb7f912893d547480fb9e6a7c62e5bfd211b'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
