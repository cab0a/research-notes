# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 6.5, 'x': 18.71, 'y': 16.9}, {'diameter': 7.4, 'x': 51.59, 'y': 44.85}], 'length': 65.0, 'thickness': 12.0, 'width': 82.0}
OPENING='top'
SOURCE_SHA256='93237a580196945cf722561b6fdfefc051f10ea0c71a5b78c6de89f98a901590'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
