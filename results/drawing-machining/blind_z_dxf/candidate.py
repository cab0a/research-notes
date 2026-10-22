# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'width': 72.0, 'length': 54.0, 'thickness': 20.0, 'features': [{'kind': 'bore', 'axis': 'z', 'u': 26.0, 'v': 22.0, 'diameter': 10.0, 'extent': 'blind', 'depth': 8.0, 'entry': 'positive'}]}
SOURCE_SHA256='3bb1a770dc33d92f57f8472722144408a134826022ecf602a43549672ad7a17d'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
