# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'depth': 7.0, 'kind': 'pocket', 'length': 26.0, 'opening': 'top', 'width': 32.0, 'x': 12.0, 'y': 12.0}, {'axis': 'z', 'diameter': 8.5, 'extent': 'through', 'kind': 'bore', 'u': 28.0, 'v': 25.0}], 'length': 64.0, 'thickness': 20.0, 'width': 94.0}
SOURCE_SHA256='fa7a6a6cd443b8f47895a27c0cd8050ee1358a2ae0b7984646a48b2cc223333e'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
