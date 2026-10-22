# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 8.0, 'x': 21.93, 'y': 13.0}, {'diameter': 8.6, 'x': 60.97, 'y': 34.5}], 'length': 50.0, 'thickness': 15.0, 'width': 96.0}
OPENING='top'
SOURCE_SHA256='e42ab77bf2c025bee4ffb470b3e7731cbc422e0382a2df5c7f9dd06842b46b24'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
