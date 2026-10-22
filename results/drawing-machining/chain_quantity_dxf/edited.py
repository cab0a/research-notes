# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'axis': 'z', 'diameter': 6.5, 'extent': 'through', 'kind': 'bore', 'u': 20.0, 'v': 18.0}, {'axis': 'z', 'diameter': 6.5, 'extent': 'through', 'kind': 'bore', 'u': 58.0, 'v': 42.0}], 'length': 60.0, 'thickness': 16.0, 'width': 88.0}
SOURCE_SHA256='56fd8cbc48658fdca49dabea25205675db8a597989c9288209bfe3e424e21e56'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
