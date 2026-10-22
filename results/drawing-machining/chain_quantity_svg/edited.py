# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'axis': 'z', 'diameter': 6.5, 'extent': 'through', 'kind': 'bore', 'u': 20.0, 'v': 18.0}, {'axis': 'z', 'diameter': 6.5, 'extent': 'through', 'kind': 'bore', 'u': 58.0, 'v': 42.0}], 'length': 60.0, 'thickness': 16.0, 'width': 88.0}
SOURCE_SHA256='2c30500e215cb8a649b008a9752d3f6cfcfcbb8273a0abf2b4ce33e081a678e7'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
