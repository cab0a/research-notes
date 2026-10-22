# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'width': 80.0, 'length': 60.0, 'thickness': 24.0, 'features': [{'kind': 'bore', 'axis': 'x', 'u': 28.0, 'v': 12.0, 'diameter': 8.0, 'extent': 'blind', 'depth': 22.0, 'entry': 'positive'}]}
SOURCE_SHA256='a053eb0f948557fd49891c66503fdb30339c0d244873fbd55fac33f233c637e9'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
