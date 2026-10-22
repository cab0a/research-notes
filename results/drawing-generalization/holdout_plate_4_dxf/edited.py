# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 7.5, 'x': 21.24, 'y': 12.48}], 'length': 48.0, 'thickness': 14.0, 'width': 93.0}
OPENING='top'
SOURCE_SHA256='d9d95d7b39ffed03d1546823dab8fdb279204ebae7fb178d6a111c5054dd32e1'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
