# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'width': 90.0, 'length': 64.0, 'thickness': 18.0, 'features': [{'kind': 'pocket', 'x': 12.0, 'y': 12.0, 'width': 32.0, 'length': 26.0, 'depth': 6.0, 'opening': 'top'}, {'kind': 'bore', 'axis': 'z', 'u': 28.0, 'v': 25.0, 'diameter': 8.0, 'extent': 'through'}]}
SOURCE_SHA256='fa7a6a6cd443b8f47895a27c0cd8050ee1358a2ae0b7984646a48b2cc223333e'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
