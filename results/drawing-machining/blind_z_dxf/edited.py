# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'axis': 'z', 'depth': 9.0, 'diameter': 10.5, 'entry': 'positive', 'extent': 'blind', 'kind': 'bore', 'u': 26.0, 'v': 22.0}], 'length': 54.0, 'thickness': 22.0, 'width': 76.0}
SOURCE_SHA256='3bb1a770dc33d92f57f8472722144408a134826022ecf602a43549672ad7a17d'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
