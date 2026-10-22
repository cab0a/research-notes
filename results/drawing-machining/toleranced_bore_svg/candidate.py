# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'width': 72.0, 'length': 54.0, 'thickness': 20.0, 'features': [{'kind': 'bore', 'axis': 'z', 'u': 26.0, 'v': 22.0, 'diameter': 10.0, 'extent': 'blind', 'depth': 8.0, 'entry': 'positive'}]}
SOURCE_SHA256='98d0a066965248877de4b6068515c836512acd512b660baca0fa7a625eeefc38'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
