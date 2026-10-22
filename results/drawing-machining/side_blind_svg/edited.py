# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'axis': 'x', 'depth': 23.0, 'diameter': 8.5, 'entry': 'positive', 'extent': 'blind', 'kind': 'bore', 'u': 28.0, 'v': 12.0}], 'length': 60.0, 'thickness': 26.0, 'width': 84.0}
SOURCE_SHA256='a053eb0f948557fd49891c66503fdb30339c0d244873fbd55fac33f233c637e9'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
