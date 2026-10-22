# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'width': 80.0, 'length': 60.0, 'thickness': 24.0, 'features': [{'kind': 'bore', 'axis': 'x', 'u': 28.0, 'v': 12.0, 'diameter': 8.0, 'extent': 'through'}]}
SOURCE_SHA256='30a1974a1f7215a974727a9ab80d070dfe26d1269e260fcd6dbf4d1c3f3393ea'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
