# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'axis': 'z', 'depth': 9.0, 'diameter': 10.5, 'entry': 'positive', 'extent': 'blind', 'kind': 'bore', 'u': 26.0, 'v': 22.0}], 'length': 54.0, 'thickness': 22.0, 'width': 76.0}
SOURCE_SHA256='53f296aca6bac9898af3e8db93050a7900ecea31bd9d85727dd0de4ac4104329'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
