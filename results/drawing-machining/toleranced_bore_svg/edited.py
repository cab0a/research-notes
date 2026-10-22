# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'axis': 'z', 'depth': 9.0, 'diameter': 10.5, 'entry': 'positive', 'extent': 'blind', 'kind': 'bore', 'u': 26.0, 'v': 22.0}], 'length': 54.0, 'thickness': 22.0, 'width': 76.0}
SOURCE_SHA256='98d0a066965248877de4b6068515c836512acd512b660baca0fa7a625eeefc38'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
