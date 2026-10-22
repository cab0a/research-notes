# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'width': 84.0, 'length': 60.0, 'thickness': 14.0, 'features': [{'kind': 'bore', 'axis': 'z', 'u': 20.0, 'v': 18.0, 'diameter': 6.0, 'extent': 'through'}, {'kind': 'bore', 'axis': 'z', 'u': 58.0, 'v': 42.0, 'diameter': 6.0, 'extent': 'through'}]}
SOURCE_SHA256='56fd8cbc48658fdca49dabea25205675db8a597989c9288209bfe3e424e21e56'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
